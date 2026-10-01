#!/usr/bin/env python3
"""
Leave-one-sensor-out ablation (Reviewer 1, Section 3.3).

Gini importance shows each channel is used by the fitted forest; it does not
show that none is redundant. This refits the classifier on every subset of
the three MQ channels and reports the accuracy cost of dropping each one,
which is the question the reviewer actually asked.

Run over ten seeds so the drops carry the same seed-sweep intervals as the
rest of the paper, and report per-class F1 for the dropped-channel models so
the mechanism of each loss is visible rather than just its size.
"""

import argparse
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_val_score

DATA = Path("data")      # overridden by --data-dir
OUT = Path("results")    # overridden by --out-dir
N_SEEDS, N_EST, N_SPLITS = 10, 100, 5
MQ = ["MQ3_V", "MQ9_V", "MQ135_V"]
RH = "Humidity_pct"
NAME = {"MQ3_V": "MQ-3", "MQ9_V": "MQ-9", "MQ135_V": "MQ-135", RH: "humidity"}

PRIMARY = {
    "Acetone": ("MQ-3_Sensor_Data_Acetone_80.csv", "MQ-3_Sensor_Data_Acetone_20.csv"),
    "Acetic_Acid": ("Acetic_Acid_80_Data.csv", "Acetic_Acid_20_Data.csv"),
    "Ammonia": ("MQ-3_Sensor_Data_Ammonia_80.csv", "MQ-3_Sensor_Data_Ammonia_20.csv"),
    "Distilled_Water": ("MQ-3_Sensor_Data_Distilled_Water_80.csv",
                        "MQ-3_Sensor_Data_Distilled_Water_20.csv"),
    "Ethanol": ("Ethanol_80_Sensor_Data.csv", "Ethanol_20_Sensor_Data.csv"),
    "Ethyl_Acetate": ("Ethyl_Acetate_80_Sensor_Data.csv", "Ethyl_Acetate_20.csv"),
    "Glycerol": ("Glycerol_80_Data.csv", "Glycerol_20_Sensor_Data.csv"),
    "Hydrogen_Peroxide": ("Hydrogen_Peroxide_80_Sensor_Data.csv",
                          "Hydrogen_Peroxide_20.csv"),
    "Propylene_Glycol": ("Propylene_Glycol_80_Data.csv",
                         "Propylene_Glycol_20_Sensor_Data.csv"),
}
DISPLAY = {"Acetic_Acid": "Acetic acid", "Acetone": "Acetone", "Ammonia": "Ammonia",
           "Distilled_Water": "Distilled water", "Ethanol": "Ethanol",
           "Ethyl_Acetate": "Ethyl acetate", "Glycerol": "Glycerol",
           "Hydrogen_Peroxide": "Hydrogen peroxide",
           "Propylene_Glycol": "Propylene glycol"}


def load():
    fr = []
    for a, files in PRIMARY.items():
        for f in files:
            d = pd.read_csv(DATA / f)
            d["Analyte"] = a
            fr.append(d)
    return pd.concat(fr, ignore_index=True)


def sweep(X, y):
    acc = []
    for s in range(N_SEEDS):
        cv = StratifiedKFold(N_SPLITS, shuffle=True, random_state=s)
        clf = RandomForestClassifier(N_EST, random_state=s)
        acc.append(cross_val_score(clf, X, y, cv=cv).mean() * 100)
    a = np.array(acc)
    return a.mean(), a.std(ddof=1), a.min(), a.max()


def per_class_f1(X, y, classes):
    cv = StratifiedKFold(N_SPLITS, shuffle=True, random_state=42)
    clf = RandomForestClassifier(N_EST, random_state=42)
    pred = cross_val_predict(clf, X, y, cv=cv)
    f1 = f1_score(y, pred, labels=classes, average=None, zero_division=0)
    return dict(zip(classes, f1))


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
    y = df["Analyte"].values
    classes = sorted(set(y))
    print(f"n = {len(df)}, classes = {len(classes)}\n")

    full_mean, full_sd, full_lo, full_hi = sweep(df[MQ].values, y)
    full_f1 = per_class_f1(df[MQ].values, y, classes)
    print("LEAVE-ONE-SENSOR-OUT, three MOS channels, ten seeds")
    print(f"{'channels retained':34s} {'acc %':>16s} {'range':>14s} {'cost':>7s}")
    print(f"{'all three (reference)':34s} "
          f"{full_mean:7.2f} +/- {full_sd:4.2f} "
          f"{full_lo:6.2f}-{full_hi:5.2f} {'—':>7s}")

    rows, f1s = [], {}
    for drop in MQ:
        keep = [c for c in MQ if c != drop]
        m, sd, lo, hi = sweep(df[keep].values, y)
        rows.append({"dropped": NAME[drop], "retained": ", ".join(NAME[k] for k in keep),
                     "mean": m, "sd": sd, "min": lo, "max": hi,
                     "cost": full_mean - m})
        f1s[NAME[drop]] = per_class_f1(df[keep].values, y, classes)
        print(f"{'without ' + NAME[drop]:34s} {m:7.2f} +/- {sd:4.2f} "
              f"{lo:6.2f}-{hi:5.2f} {full_mean - m:+7.2f}")

    print("\nSINGLE CHANNELS (context for how much each carries alone)")
    singles = {}
    for c in MQ:
        m, sd, lo, hi = sweep(df[[c]].values, y)
        singles[NAME[c]] = {"mean": m, "sd": sd, "min": lo, "max": hi}
        print(f"{NAME[c] + ' alone':34s} {m:7.2f} +/- {sd:4.2f} {lo:6.2f}-{hi:5.2f}")

    print("\nWITH HUMIDITY, to show the same test on the four-feature model")
    four_mean, four_sd, four_lo, four_hi = sweep(df[MQ + [RH]].values, y)
    print(f"{'all four (reference)':34s} {four_mean:7.2f} +/- {four_sd:4.2f} "
          f"{four_lo:6.2f}-{four_hi:5.2f}")
    four_rows = []
    for drop in MQ + [RH]:
        keep = [c for c in MQ + [RH] if c != drop]
        m, sd, lo, hi = sweep(df[keep].values, y)
        four_rows.append({"dropped": NAME[drop], "mean": m, "sd": sd,
                          "min": lo, "max": hi, "cost": four_mean - m})
        print(f"{'without ' + NAME[drop]:34s} {m:7.2f} +/- {sd:4.2f} "
              f"{lo:6.2f}-{hi:5.2f} {four_mean - m:+7.2f}")

    print("\nPER-CLASS F1 WHEN A CHANNEL IS DROPPED (seed 42, three-channel model)")
    hdr = f"{'analyte':20s} {'all three':>10s}" + "".join(
        f"{'-' + k:>12s}" for k in f1s)
    print(hdr)
    for c in classes:
        line = f"{DISPLAY[c]:20s} {full_f1[c]:10.3f}"
        for k in f1s:
            line += f"{f1s[k][c]:12.3f}"
        print(line)

    (OUT / "loso_results.json").write_text(json.dumps({
        "full": {"mean": full_mean, "sd": full_sd, "min": full_lo, "max": full_hi},
        "drop_one_of_three": rows,
        "single_channels": singles,
        "four_feature_full": {"mean": four_mean, "sd": four_sd,
                              "min": four_lo, "max": four_hi},
        "drop_one_of_four": four_rows,
        "per_class_f1_full": {DISPLAY[c]: full_f1[c] for c in classes},
        "per_class_f1_dropped": {k: {DISPLAY[c]: v[c] for c in classes}
                                 for k, v in f1s.items()},
    }, indent=2))
    print(f"\nwrote {OUT / 'loso_results.json'}")


if __name__ == "__main__":
    main()
