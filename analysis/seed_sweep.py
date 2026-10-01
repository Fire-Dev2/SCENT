#!/usr/bin/env python3
"""
Seed sweep for the SCENT manuscript.

Ten seeds, four feature sets. The CV splitter and the forest share the seed,
so each seed is a full re-randomization of both fold assignment and bootstrap.

Paired comparisons use cross_val_predict with the SAME splitter object per seed,
so out-of-fold predictions are aligned trial-for-trial and McNemar is valid.
cross_val_score cannot give paired predictions, so both are computed.

Feature sets
  A  primary  n=450  3 MQ channels
  B  primary  n=450  3 MQ channels + BME680 relative humidity
  C  ablation n=245  raw divider voltage
  D  ablation n=245  Rs/R0

Paired tests
  B vs A   humidity fusion
  D vs C   resistance-ratio normalization
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (StratifiedKFold, cross_val_predict,
                                     cross_val_score)
from statsmodels.stats.contingency_tables import mcnemar

DATA = Path("data")      # overridden by --data-dir
OUT = Path("results")    # overridden by --out-dir
N_SEEDS = 10
N_ESTIMATORS = 100
N_SPLITS = 5
VC = 5.0

MQ = ["MQ3_V", "MQ9_V", "MQ135_V"]
R0 = ["MQ3_R0", "MQ9_R0", "MQ135_R0"]
RH = "Humidity_pct"

PRIMARY = {
    "Acetone":           ("MQ-3_Sensor_Data_Acetone_80.csv", "MQ-3_Sensor_Data_Acetone_20.csv"),
    "Acetic_Acid":       ("Acetic_Acid_80_Data.csv", "Acetic_Acid_20_Data.csv"),
    "Ammonia":           ("MQ-3_Sensor_Data_Ammonia_80.csv", "MQ-3_Sensor_Data_Ammonia_20.csv"),
    "Distilled_Water":   ("MQ-3_Sensor_Data_Distilled_Water_80.csv", "MQ-3_Sensor_Data_Distilled_Water_20.csv"),
    "Ethanol":           ("Ethanol_80_Sensor_Data.csv", "Ethanol_20_Sensor_Data.csv"),
    "Ethyl_Acetate":     ("Ethyl_Acetate_80_Sensor_Data.csv", "Ethyl_Acetate_20.csv"),
    "Glycerol":          ("Glycerol_80_Data.csv", "Glycerol_20_Sensor_Data.csv"),
    "Hydrogen_Peroxide": ("Hydrogen_Peroxide_80_Sensor_Data.csv", "Hydrogen_Peroxide_20.csv"),
    "Propylene_Glycol":  ("Propylene_Glycol_80_Data.csv", "Propylene_Glycol_20_Sensor_Data.csv"),
}


def load_primary():
    frames = []
    for analyte, (fa, fb) in PRIMARY.items():
        for fname, batch in ((fa, "A"), (fb, "B")):
            d = pd.read_csv(DATA / fname)
            d["Analyte"] = analyte
            d["Batch"] = batch
            frames.append(d)
    return pd.concat(frames, ignore_index=True)


def load_ablation():
    d = pd.read_csv(DATA / "New_Protocol_Dataset.csv")
    d["Analyte"] = d["Label"]
    for v, r in zip(MQ, R0):
        rs_rl = (VC / d[v]) - 1.0
        d[v.replace("_V", "_ratio")] = rs_rl / d[r]
    return d


def sweep(X, y, label):
    """Return per-seed accuracy and out-of-fold predictions keyed by seed."""
    accs, preds = {}, {}
    for seed in range(N_SEEDS):
        cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
        clf = RandomForestClassifier(n_estimators=N_ESTIMATORS, random_state=seed)
        accs[seed] = cross_val_score(clf, X, y, cv=cv).mean() * 100
        # same splitter parameters -> identical folds for the paired partner
        cv2 = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=seed)
        clf2 = RandomForestClassifier(n_estimators=N_ESTIMATORS, random_state=seed)
        preds[seed] = cross_val_predict(clf2, X, y, cv=cv2)
    v = np.array(list(accs.values()))
    print(f"{label:34s} min {v.min():6.2f}  max {v.max():6.2f}  "
          f"range {v.max()-v.min():5.2f}  mean {v.mean():6.2f} +/- {v.std(ddof=1):.2f}")
    return accs, preds


def paired_mcnemar(y, preds_a, preds_b, label):
    """Per-seed McNemar, b = candidate, a = reference."""
    ps, b01s, b10s = [], [], []
    for seed in range(N_SEEDS):
        ca = preds_a[seed] == y
        cb = preds_b[seed] == y
        n01 = int((~ca & cb).sum())   # a wrong, b right
        n10 = int((ca & ~cb).sum())   # a right, b wrong
        tbl = [[int((ca & cb).sum()), n10], [n01, int((~ca & ~cb).sum())]]
        # exact binomial when discordant count is small, chi2 otherwise
        exact = (n01 + n10) < 25
        p = float(mcnemar(tbl, exact=exact, correction=not exact).pvalue)
        ps.append(p); b01s.append(n01); b10s.append(n10)
    ps = np.array(ps)
    print(f"{label:34s} p min {ps.min():.3g}  max {ps.max():.3g}  "
          f"median {np.median(ps):.3g}   discordant b+/b- "
          f"{np.mean(b01s):.1f}/{np.mean(b10s):.1f}")
    return ps


def main():
    global DATA, OUT
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="data",
                    help="directory holding the deposited CSVs")
    ap.add_argument("--out-dir", default="results",
                    help="directory to write the results JSON into")
    args = ap.parse_args()
    DATA, OUT = Path(args.data_dir), Path(args.out_dir)
    OUT.mkdir(parents=True, exist_ok=True)

    prim = load_primary()
    abl = load_ablation()

    print(f"primary  n={len(prim)}  classes={prim['Analyte'].nunique()}  "
          f"per-class={sorted(prim['Analyte'].value_counts().unique())}")
    print(f"ablation n={len(abl)}  classes={abl['Analyte'].nunique()}  "
          f"per-class={sorted(abl['Analyte'].value_counts().unique())}")
    print()

    yp = prim["Analyte"].values
    ya = abl["Analyte"].values

    XA = prim[MQ].values
    XB = prim[MQ + [RH]].values
    XC = abl[MQ].values
    XD = abl[[c.replace("_V", "_ratio") for c in MQ]].values

    print("ACCURACY ACROSS 10 SEEDS")
    accA, pA = sweep(XA, yp, "A  primary  3-MOS")
    accB, pB = sweep(XB, yp, "B  primary  3-MOS + humidity")
    accC, pC = sweep(XC, ya, "C  ablation raw voltage")
    accD, pD = sweep(XD, ya, "D  ablation Rs/R0")

    print()
    print("PER-SEED McNEMAR")
    pHum = paired_mcnemar(yp, pA, pB, "B vs A  humidity fusion")
    pNorm = paired_mcnemar(ya, pC, pD, "D vs C  Rs/R0 normalization")

    out = {
        "n_seeds": N_SEEDS,
        "accuracy": {
            k: {"per_seed": v, "min": min(v.values()), "max": max(v.values()),
                "mean": float(np.mean(list(v.values()))),
                "sd": float(np.std(list(v.values()), ddof=1))}
            for k, v in [("A_primary_3MOS", accA), ("B_primary_3MOS_humidity", accB),
                         ("C_ablation_raw", accC), ("D_ablation_RsR0", accD)]
        },
        "mcnemar": {
            "humidity_fusion_B_vs_A": {"per_seed": pHum.tolist(),
                                       "min": float(pHum.min()), "max": float(pHum.max())},
            "normalization_D_vs_C": {"per_seed": pNorm.tolist(),
                                     "min": float(pNorm.min()), "max": float(pNorm.max())},
        },
    }
    (OUT / "seed_sweep_results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
