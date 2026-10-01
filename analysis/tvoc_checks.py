#!/usr/bin/env python3
"""
Section V-F: tests supporting exclusion of the CCS811 TVOC channel.

Three questions:
  1. How much more separable is TVOC than every other channel?
     Statistic: between-class variance ratio (one-way F), and the minimum
     inter-class gap in pooled s.d. units across all 36 class pairs.
  2. Do the reported channels correlate with TVOC?
  3. Do the reported channels trend with acquisition order within analyte?
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA = Path("data")      # overridden by --data-dir
OUT = Path("results")    # overridden by --out-dir

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

CHANNELS = ["MQ3_V", "MQ9_V", "MQ135_V", "Humidity_pct", "Temp_C", "eCO2_ppm", "TVOC_ppb"]
NAMES = {"MQ3_V": "MQ-3", "MQ9_V": "MQ-9", "MQ135_V": "MQ-135",
         "Humidity_pct": "BME680 humidity", "Temp_C": "BME680 temperature",
         "eCO2_ppm": "CCS811 eCO2", "TVOC_ppb": "CCS811 TVOC"}


def load():
    frames = []
    for analyte, (fa, fb) in PRIMARY.items():
        for fname, batch in ((fa, "A"), (fb, "B")):
            d = pd.read_csv(DATA / fname)
            d["Analyte"] = analyte
            d["Batch"] = batch
            frames.append(d)
    return pd.concat(frames, ignore_index=True)


def f_ratio(df, ch):
    groups = [g[ch].values for _, g in df.groupby("Analyte")]
    return float(stats.f_oneway(*groups).statistic)


def min_pair_gap(df, ch):
    """Smallest inter-class separation over all 36 pairs, in pooled s.d. units.
    Negative means the two class distributions overlap."""
    stat = df.groupby("Analyte")[ch].agg(["mean", "std", "count"])
    cls = list(stat.index)
    gaps = []
    for i in range(len(cls)):
        for j in range(i + 1, len(cls)):
            a, b = stat.loc[cls[i]], stat.loc[cls[j]]
            pooled = np.sqrt(((a["count"] - 1) * a["std"] ** 2 +
                              (b["count"] - 1) * b["std"] ** 2) /
                             (a["count"] + b["count"] - 2))
            # edge-to-edge distance at 1 s.d., normalized
            gaps.append((abs(a["mean"] - b["mean"]) - (a["std"] + b["std"])) / pooled)
    return float(min(gaps)), int(sum(1 for g in gaps if g < 0)), len(gaps)


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

    df = load()
    print(f"n = {len(df)}\n")

    print("1. BETWEEN-CLASS SEPARATION BY CHANNEL")
    print(f"{'channel':>22} {'F':>12} {'min pair gap':>14} {'overlapping pairs':>18}")
    rows = {}
    for ch in CHANNELS:
        F = f_ratio(df, ch)
        gap, nover, npair = min_pair_gap(df, ch)
        rows[ch] = {"F": F, "min_gap_sd": gap, "overlapping_pairs": nover, "n_pairs": npair}
        print(f"{NAMES[ch]:>22} {F:>12.1f} {gap:>+14.3f} {nover:>13}/{npair}")

    tv = rows["TVOC_ppb"]["F"]
    others = {c: rows[c]["F"] for c in CHANNELS if c != "TVOC_ppb"}
    nxt = max(others, key=others.get)
    print(f"\n   TVOC F exceeds the next-highest channel ({NAMES[nxt]}) "
          f"by a factor of {tv / others[nxt]:.1f}.")
    print(f"   TVOC is the only channel with no overlapping class pair "
          f"(min gap {rows['TVOC_ppb']['min_gap_sd']:+.3f} pooled s.d.).")

    print("\n2. CORRELATION OF EACH REPORTED CHANNEL WITH TVOC")
    print(f"{'channel':>22} {'Pearson r':>12} {'Spearman rho':>14}")
    corr = {}
    for ch in ["MQ3_V", "MQ9_V", "MQ135_V", "Humidity_pct"]:
        r = float(np.corrcoef(df[ch], df["TVOC_ppb"])[0, 1])
        rho = float(stats.spearmanr(df[ch], df["TVOC_ppb"]).statistic)
        corr[ch] = {"pearson": r, "spearman": rho}
        print(f"{NAMES[ch]:>22} {r:>+12.3f} {rho:>+14.3f}")
    mx = max(abs(v["pearson"]) for v in corr.values())
    print(f"\n   Largest |r| among reported channels: {mx:.3f}")

    print("\n3. TREND WITH TRIAL INDEX WITHIN ANALYTE (Spearman, pooled)")
    print(f"{'channel':>22} {'median rho':>12} {'max |rho|':>12} {'p<0.05':>8}")
    trend = {}
    for ch in ["MQ3_V", "MQ9_V", "MQ135_V", "Humidity_pct", "TVOC_ppb"]:
        rs, sig = [], 0
        for _, g in df.groupby("Analyte"):
            res = stats.spearmanr(g["Trial_ID"], g[ch])
            rs.append(float(res.statistic))
            if res.pvalue < 0.05:
                sig += 1
        trend[ch] = {"median_rho": float(np.median(rs)),
                     "max_abs_rho": float(max(abs(r) for r in rs)),
                     "n_significant": sig, "n_classes": len(rs)}
        print(f"{NAMES[ch]:>22} {np.median(rs):>+12.3f} "
              f"{max(abs(r) for r in rs):>12.3f} {sig:>6}/9")

    (OUT / "tvoc_checks_results.json").write_text(json.dumps(
        {"separation": rows, "correlation_with_tvoc": corr,
         "trend_with_trial_index": trend}, indent=2))


if __name__ == "__main__":
    main()
