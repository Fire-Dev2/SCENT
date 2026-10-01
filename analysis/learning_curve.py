#!/usr/bin/env python3
"""
Learning curve for the SCENT manuscript, Fig. 8 / Section IV-I.

Diagnoses whether the reported 65.8% -> 89.8% rise between 258 and 360
training trials is real or an artifact of unstratified subset construction.

Procedure as described in Section III-B:
  for each of the five outer folds
    draw a random subset of the fold's TRAINING portion at the stated size
    fit the classifier to the subset
    score the FULL held-out fold
  plot mean and s.d. across the five folds

Run twice: subsets drawn stratified by class, and drawn without stratification.
If the two differ at small sizes, the reported curve was unstratified.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, train_test_split

DATA = Path("data")      # overridden by --data-dir
OUT = Path("results")    # overridden by --out-dir
SEED = 42
N_ESTIMATORS = 100
N_SPLITS = 5
N_REPEATS = 8          # subset draws averaged at each size, per fold

MQ = ["MQ3_V", "MQ9_V", "MQ135_V"]
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

SIZES = [45, 90, 135, 180, 225, 258, 270, 315, 360]


def load_primary():
    frames = []
    for analyte, (fa, fb) in PRIMARY.items():
        for fname in (fa, fb):
            df = pd.read_csv(DATA / fname)
            df["Analyte"] = analyte
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def curve(X, y, stratify, sizes=SIZES):
    """Mean and s.d. of held-out fold accuracy across the five folds."""
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    out = {s: [] for s in sizes}
    for fold, (tr, te) in enumerate(cv.split(X, y)):
        Xtr, ytr, Xte, yte = X[tr], y[tr], X[te], y[te]
        for size in sizes:
            if size > len(tr):
                continue
            accs = []
            for rep in range(N_REPEATS):
                rs = SEED + rep
                if size == len(tr):
                    Xs, ys = Xtr, ytr
                else:
                    Xs, _, ys, _ = train_test_split(
                        Xtr, ytr, train_size=size, random_state=rs,
                        stratify=ytr if stratify else None)
                clf = RandomForestClassifier(n_estimators=N_ESTIMATORS, random_state=rs)
                clf.fit(Xs, ys)
                accs.append(clf.score(Xte, yte))
            out[size].append(np.mean(accs))
    return {s: (np.mean(v) * 100, np.std(v, ddof=1) * 100) for s, v in out.items() if v}


def class_coverage(y, size, stratify, n_draws=200):
    """How many of the nine classes appear in a subset of this size, and the
    minimum per-class count. Diagnoses whether unstratified draws starve classes."""
    ncls, mincount = [], []
    for rep in range(n_draws):
        if size >= len(y):
            ys = y
        else:
            _, _, ys, _ = train_test_split(
                np.zeros((len(y), 1)), y, train_size=size, random_state=rep,
                stratify=y if stratify else None)
        vc = pd.Series(ys).value_counts()
        ncls.append(len(vc))
        mincount.append(vc.min() if len(vc) == 9 else 0)
    return np.mean(ncls), np.mean(mincount)


def per_class_at(X, y, size, stratify):
    """Per-class held-out accuracy at one training size, pooled over folds."""
    cv = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    correct, total = {}, {}
    for tr, te in cv.split(X, y):
        Xtr, ytr, Xte, yte = X[tr], y[tr], X[te], y[te]
        for rep in range(N_REPEATS):
            rs = SEED + rep
            if size >= len(tr):
                Xs, ys = Xtr, ytr
            else:
                Xs, _, ys, _ = train_test_split(
                    Xtr, ytr, train_size=size, random_state=rs,
                    stratify=ytr if stratify else None)
            clf = RandomForestClassifier(n_estimators=N_ESTIMATORS, random_state=rs)
            clf.fit(Xs, ys)
            pred = clf.predict(Xte)
            for cls in np.unique(y):
                m = yte == cls
                correct[cls] = correct.get(cls, 0) + int((pred[m] == cls).sum())
                total[cls] = total.get(cls, 0) + int(m.sum())
    return {c: 100 * correct[c] / total[c] for c in sorted(correct)}


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

    df = load_primary()
    y = df["Analyte"].values
    X3 = df[MQ].values
    X4 = df[MQ + [RH]].values

    print(f"n = {len(df)}, classes = {len(np.unique(y))}, "
          f"training portion per fold = {len(df) - len(df)//N_SPLITS}\n")

    print("SUBSET CLASS COVERAGE (training portion = 360, nine classes)")
    print(f"{'size':>6} {'strat: classes':>16} {'min/class':>10} "
          f"{'unstrat: classes':>18} {'min/class':>10}")
    for s in [45, 90, 180, 258, 315]:
        ns, ms = class_coverage(y[:360], s, True)
        nu, mu = class_coverage(y[:360], s, False)
        print(f"{s:>6} {ns:>16.2f} {ms:>10.1f} {nu:>18.2f} {mu:>10.1f}")
    print()

    results = {}
    for name, X in [("3-MOS", X3), ("3-MOS + humidity", X4)]:
        for strat in (True, False):
            key = f"{name} | {'stratified' if strat else 'unstratified'}"
            results[key] = curve(X, y, strat)

    print("LEARNING CURVE, held-out fold accuracy (%), mean +/- s.d. across folds")
    hdr = f"{'size':>6}"
    for k in results:
        hdr += f" {k.split('|')[0].strip()[:9] + '/' + k.split('|')[1].strip()[:6]:>18}"
    print(hdr)
    for s in SIZES:
        row = f"{s:>6}"
        for k in results:
            if s in results[k]:
                m, sd = results[k][s]
                row += f" {m:>11.1f} +/-{sd:>4.1f}"
            else:
                row += f" {'-':>18}"
        print(row)
    print()

    print("REPORTED IN MANUSCRIPT: 3-MOS 65.8 at 258 -> 89.8 at 360; "
          "4-ch 77.1 -> 99.6")
    for k in results:
        if 258 in results[k] and 360 in results[k]:
            a, b = results[k][258][0], results[k][360][0]
            print(f"  {k:36s} {a:5.1f} -> {b:5.1f}   rise {b-a:+5.1f}")
    print()

    print("PER-CLASS HELD-OUT ACCURACY AT 258 TRAINING TRIALS (stratified)")
    pc3 = per_class_at(X3, y, 258, True)
    pc4 = per_class_at(X4, y, 258, True)
    print(f"{'class':>20} {'3-MOS':>8} {'+humidity':>10}")
    for c in pc3:
        print(f"{c:>20} {pc3[c]:>8.1f} {pc4[c]:>10.1f}")
    print(f"{'MEAN':>20} {np.mean(list(pc3.values())):>8.1f} "
          f"{np.mean(list(pc4.values())):>10.1f}")

    (OUT / "learning_curve_results.json").write_text(json.dumps({
        "curves": {k: {str(s): list(v) for s, v in d.items()} for k, d in results.items()},
        "per_class_at_258_stratified": {"3MOS": pc3, "3MOS_humidity": pc4},
    }, indent=2))


if __name__ == "__main__":
    main()
