#!/usr/bin/env python3
"""
SCENT: nine-class chemical headspace classification from a low-cost MOS sensor array.

Reproduces every value and figure reported in the manuscript.

  Primary dataset (450 trials, 9 analytes, 3 MQ channels)
    five-fold stratified CV accuracy and macro F1; exact binomial and
    label-permutation tests against chance; per-class precision/recall (Table II);
    pooled out-of-fold confusion matrix (Fig. 2); Gini channel importances (Fig. S1);
    batch holdout across acquisition days; seven-classifier comparison (Table S1).

  Ablation dataset (245 trials, per-trial clean-air R0 recorded)
    raw divider voltage vs Rs/R0 features (Table I); McNemar and paired t tests;
    per-class F1 under both representations (Table S2); confusion matrices (Fig. S2).

  Humidity fusion (both datasets)
    BME680 relative humidity as a fourth feature (Fig. 3, Table S3);
    McNemar against the three-channel model.

Usage:
    python scent_analysis.py --data-dir ../data --out-dir ../figures
    python scent_analysis.py --data-dir ../data --out-dir ../figures --permutations 200

Deterministic under the fixed seed. Runtime is a few minutes, dominated by the
permutation test; lower --permutations to shorten it.
"""

import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import (StratifiedKFold, cross_val_predict,
                                     cross_val_score, permutation_test_score)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

RANDOM_STATE = 42
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
ABLATION = "New_Protocol_Dataset.csv"

DISPLAY = {"Acetic_Acid":"Acetic acid","Acetone":"Acetone","Ammonia":"Ammonia",
 "Distilled_Water":"Distilled water","Ethanol":"Ethanol","Ethyl_Acetate":"Ethyl acetate",
 "Glycerol":"Glycerol","Hydrogen_Peroxide":"Hydrogen peroxide","Propylene_Glycol":"Propylene glycol"}
CHANNEL = {"MQ3_V":"MQ-3 (alcohol)","MQ9_V":"MQ-9 (combustible aliphatics, CO)",
 "MQ135_V":"MQ-135 (air quality / NH3)", RH:"BME680 (relative humidity)"}


def rf():
    return RandomForestClassifier(n_estimators=N_ESTIMATORS, random_state=RANDOM_STATE)

def folds():
    return StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)


def load_primary(data_dir):
    frames, missing = [], []
    for analyte, (fa, fb) in PRIMARY.items():
        for fname, batch in ((fa, "A"), (fb, "B")):
            p = data_dir / fname
            if not p.exists():
                missing.append(fname); continue
            d = pd.read_csv(p); d["Analyte"] = analyte; d["Batch"] = batch
            frames.append(d)
    if missing:
        sys.exit(f"Missing {len(missing)} primary file(s) in {data_dir}:\n  " + "\n  ".join(missing))
    return pd.concat(frames, ignore_index=True)


def load_ablation(data_dir):
    p = data_dir / ABLATION
    if not p.exists():
        sys.exit(f"Missing ablation dataset: {p}")
    d = pd.read_csv(p)
    d["Analyte"] = d["Label"].str.replace(" ", "_")
    return d


def rs_over_r0(df):
    """Rs/RL = (Vc/Vout - 1), divided by the per-trial R0 of the same channel.
    R0 is logged in load-resistor units, so RL cancels."""
    rs = np.column_stack([(VC / df[c].values - 1) for c in MQ])
    return rs / df[R0].values


def integrity(df, name, feats):
    counts = df["Analyte"].value_counts()
    n_dup = int(df.duplicated(subset=feats).sum())
    print(f"=== {name}: integrity ===")
    print(f"  trials {len(df)}, classes {counts.size}, per class {counts.min()}-{counts.max()}")
    print(f"  exact duplicate feature rows: {n_dup}")
    flagged = []
    for a in sorted(df["Analyte"].unique()):
        s = df[df["Analyte"] == a]
        spread = float(s["MQ3_V"].max() - s["MQ3_V"].min())
        if spread < 0.005:
            flagged.append((a, spread))
    if flagged:
        print("  LOW-VARIANCE WARNING (possible derived or replicated rows):")
        for a, s in flagged:
            print(f"    {a}: MQ3_V spread {s:.5f} V")
    else:
        print("  per-analyte MQ3_V spread: all above quantisation floor")
    print()
    return {"n": int(len(df)), "duplicates": n_dup,
            "low_variance_analytes": [a for a, _ in flagged]}


def analyse_primary(df, n_perm):
    from scipy.stats import binomtest
    X, y = df[MQ].values, df["Analyte"].values
    classes = sorted(set(y)); chance = 1.0 / len(classes); cv = folds()

    acc = cross_val_score(rf(), X, y, cv=cv, scoring="accuracy")
    f1  = cross_val_score(rf(), X, y, cv=cv, scoring="f1_macro")
    yp  = cross_val_predict(rf(), X, y, cv=cv)
    ncorr = int((yp == y).sum())

    print("=== Primary dataset, three MQ channels ===")
    print(f"  accuracy {acc.mean()*100:.1f} +/- {acc.std()*100:.1f}%   macro F1 {f1.mean():.3f} +/- {f1.std():.3f}")
    print(f"  folds {np.round(acc,4)}")
    print(f"  {ncorr}/{len(y)} correct; chance {chance*100:.1f}%")
    bp = binomtest(ncorr, len(y), chance, alternative="greater").pvalue
    print(f"  exact binomial p = {bp:.3e}")

    score, perm, pp = permutation_test_score(rf(), X, y, scoring="accuracy", cv=cv,
        n_permutations=n_perm, random_state=RANDOM_STATE, n_jobs=-1)
    print(f"  permutation ({n_perm}): permuted {perm.mean()*100:.1f} +/- {perm.std()*100:.1f}%, "
          f"max {perm.max()*100:.1f}%, p = {pp:.4f}")
    print(f"    (minimum attainable p = {1/(n_perm+1):.4f})")

    a, b = df[df.Batch=="A"], df[df.Batch=="B"]
    ho = accuracy_score(b["Analyte"], rf().fit(a[MQ], a["Analyte"]).predict(b[MQ]))
    print(f"  batch holdout (train day 1 -> test day 2): {ho*100:.1f}%")

    imp = dict(zip(MQ, rf().fit(X, y).feature_importances_.tolist()))
    print("  Gini importances: " + ", ".join(f"{k} {v:.3f}" for k, v in imp.items()))
    print(); print(classification_report(y, yp, digits=3))

    rep = classification_report(y, yp, output_dict=True, digits=3)
    return {"classes":classes,"chance":chance,
            "accuracy_mean":float(acc.mean()),"accuracy_std":float(acc.std()),
            "macro_f1_mean":float(f1.mean()),"macro_f1_std":float(f1.std()),
            "n_correct":ncorr,"n_total":int(len(y)),"binomial_p":float(bp),
            "permutation_p":float(pp),"permuted_mean":float(perm.mean()),
            "permuted_std":float(perm.std()),"permuted_max":float(perm.max()),
            "batch_holdout":float(ho),"importances":imp,
            "per_class":{c:rep[c] for c in classes},
            "confusion_matrix":confusion_matrix(y,yp,labels=classes).tolist()}


def compare_classifiers(df):
    X, y = df[MQ].values, df["Analyte"].values
    cv = folds()
    models = {
      "Support vector machine (RBF)": make_pipeline(StandardScaler(), SVC(kernel="rbf", random_state=RANDOM_STATE)),
      "Support vector machine (linear)": make_pipeline(StandardScaler(), SVC(kernel="linear", random_state=RANDOM_STATE)),
      "Gaussian naive Bayes": make_pipeline(StandardScaler(), GaussianNB()),
      "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)),
      "k-nearest neighbors (k = 5)": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=5)),
      "Decision tree": DecisionTreeClassifier(random_state=RANDOM_STATE),
      "Random forest (100 trees, deployed)": rf(),
    }
    print("=== Classifier comparison, identical folds (Table S1) ===")
    out = {}
    for name, m in models.items():
        a = cross_val_score(m, X, y, cv=cv, scoring="accuracy")
        f = cross_val_score(m, X, y, cv=cv, scoring="f1_macro")
        out[name] = {"accuracy_mean":float(a.mean()),"accuracy_std":float(a.std()),
                     "macro_f1":float(f.mean())}
        print(f"  {name:36s} {a.mean()*100:5.1f} +/- {a.std()*100:4.1f}%   F1 {f.mean():.3f}")
    print()
    return out


def analyse_ablation(df):
    from scipy.stats import ttest_rel
    from statsmodels.stats.contingency_tables import mcnemar
    y = df["Analyte"].values; classes = sorted(set(y)); cv = folds()
    sets = {"raw": df[MQ].values, "norm": rs_over_r0(df)}
    res, preds = {}, {}
    print("=== Normalization ablation ===")
    for k, X in sets.items():
        a = cross_val_score(rf(), X, y, cv=cv, scoring="accuracy")
        f = cross_val_score(rf(), X, y, cv=cv, scoring="f1_macro")
        p = cross_val_predict(rf(), X, y, cv=cv); preds[k] = p
        rep = classification_report(y, p, output_dict=True, digits=3)
        others = [c for c in classes if c not in ("Glycerol","Distilled_Water")]
        res[k] = {"accuracy_mean":float(a.mean()),"accuracy_std":float(a.std()),
                  "macro_f1":float(f.mean()),"fold_accuracies":a.tolist(),
                  "glycerol_f1":rep["Glycerol"]["f1-score"],
                  "water_f1":rep["Distilled_Water"]["f1-score"],
                  "other_seven_mean_recall":float(np.mean([rep[c]["recall"] for c in others])),
                  "per_class_f1":{c:rep[c]["f1-score"] for c in classes},
                  "support":{c:int(rep[c]["support"]) for c in classes},
                  "confusion_matrix":confusion_matrix(y,p,labels=classes).tolist()}
        r = res[k]
        print(f"  {k:5s} accuracy {r['accuracy_mean']*100:5.1f} +/- {r['accuracy_std']*100:4.1f}%   "
              f"glycerol F1 {r['glycerol_f1']:.3f}   water F1 {r['water_f1']:.3f}   "
              f"other seven recall {r['other_seven_mean_recall']:.3f}")

    ok_r, ok_n = (preds["raw"]==y), (preds["norm"]==y)
    b = int((ok_r & ~ok_n).sum()); c = int((~ok_r & ok_n).sum())
    tbl = [[int((ok_r & ok_n).sum()), b],[c, int((~ok_r & ~ok_n).sum())]]
    mp = float(mcnemar(tbl, exact=True).pvalue)
    t, tp = ttest_rel(res["raw"]["fold_accuracies"], res["norm"]["fold_accuracies"])
    print(f"  paired: both correct {tbl[0][0]}, raw only {b}, norm only {c}, both wrong {tbl[1][1]}")
    print(f"  McNemar exact p = {mp:.4f};  paired t across folds p = {tp:.4f}")
    if mp >= 0.05:
        print("  -> not significant; claim no benefit, not active degradation")

    d1, d2 = df[df.Batch_Day==1], df[df.Batch_Day==2]
    cross = {"raw": float(accuracy_score(d2["Analyte"],
                rf().fit(d1[MQ], d1["Analyte"]).predict(d2[MQ]))),
             "norm": float(accuracy_score(d2["Analyte"],
                rf().fit(rs_over_r0(d1), d1["Analyte"]).predict(rs_over_r0(d2))))}
    print(f"  cross-day holdout: raw {cross['raw']*100:.1f}%, normalized {cross['norm']*100:.1f}%")
    print()
    res.update({"mcnemar_table":tbl,"mcnemar_p":mp,"paired_t_p":float(tp),
                "cross_day":cross,"classes":classes})
    return res


def analyse_fusion(primary, ablation):
    from statsmodels.stats.contingency_tables import mcnemar
    cv = folds(); out = {}
    print("=== Humidity fusion ===")
    for name, df in (("primary", primary), ("ablation", ablation)):
        y = df["Analyte"].values; classes = sorted(set(y))
        X3, X4 = df[MQ].values, df[MQ+[RH]].values
        a3 = cross_val_score(rf(), X3, y, cv=cv, scoring="accuracy")
        a4 = cross_val_score(rf(), X4, y, cv=cv, scoring="accuracy")
        f4 = cross_val_score(rf(), X4, y, cv=cv, scoring="f1_macro")
        p3 = cross_val_predict(rf(), X3, y, cv=cv)
        p4 = cross_val_predict(rf(), X4, y, cv=cv)
        rep = classification_report(y, p4, output_dict=True, digits=3)
        ok3, ok4 = (p3==y), (p4==y)
        b = int((ok3 & ~ok4).sum()); c = int((~ok3 & ok4).sum())
        mp = float(mcnemar([[int((ok3&ok4).sum()), b],[c, int((~ok3&~ok4).sum())]],
                           exact=True).pvalue)
        e = {"three_channel_accuracy":float(a3.mean()),
             "four_channel_accuracy":float(a4.mean()),
             "four_channel_accuracy_std":float(a4.std()),
             "four_channel_macro_f1":float(f4.mean()),
             "n_correct_four":int(ok4.sum()),"n_total":int(len(y)),
             "glycerol_f1":rep["Glycerol"]["f1-score"],
             "water_f1":rep["Distilled_Water"]["f1-score"],
             "mcnemar_p":mp,"classes":classes,
             "per_class":{cl:rep[cl] for cl in classes},
             "confusion_matrix_four":confusion_matrix(y,p4,labels=classes).tolist()}
        if name == "primary":
            e["importances_four"] = dict(zip(MQ+[RH],
                rf().fit(X4, y).feature_importances_.tolist()))
            a, bb = df[df.Batch=="A"], df[df.Batch=="B"]
            e["batch_holdout_four"] = float(accuracy_score(bb["Analyte"],
                rf().fit(a[MQ+[RH]], a["Analyte"]).predict(bb[MQ+[RH]])))
        out[name] = e
        print(f"  {name:9s} 3-channel {a3.mean()*100:5.1f}% -> 4-channel "
              f"{a4.mean()*100:5.1f} +/- {a4.std()*100:.1f}%   "
              f"glycerol F1 {e['glycerol_f1']:.3f}   water F1 {e['water_f1']:.3f}   "
              f"McNemar p = {mp:.2e}")
    if "importances_four" in out["primary"]:
        print("  four-feature importances: " + ", ".join(
            f"{k} {v:.3f}" for k, v in out["primary"]["importances_four"].items()))
        print(f"  batch holdout with humidity: {out['primary']['batch_holdout_four']*100:.1f}%")
    print("\n  mean relative humidity by analyte (primary):")
    for a in sorted(primary["Analyte"].unique()):
        print(f"    {DISPLAY[a]:20s} {primary[primary.Analyte==a][RH].mean():.1f}%")
    print()
    return out


def _cm(ax, cm, labels, title, show_y=True, vmax=50):
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=vmax)
    ax.set_xticks(range(len(labels))); ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(labels if show_y else [""]*len(labels), fontsize=7)
    ax.set_xlabel("Predicted class", fontsize=8)
    if show_y: ax.set_ylabel("True class", fontsize=8)
    ax.set_title(title, fontsize=9, loc="left", fontweight="bold")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            if cm[i,j] > 0:
                ax.text(j,i,str(cm[i,j]),ha="center",va="center",fontsize=6,
                        color="white" if cm[i,j] > vmax/2 else "black")
    return im


def make_figures(pr, ab, fu, out_dir):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["font.family"] = "DejaVu Sans"
    labels = [DISPLAY[c] for c in pr["classes"]]

    fig, ax = plt.subplots(figsize=(6.5,5.5))
    im = _cm(ax, np.array(pr["confusion_matrix"]), labels,
             f"Confusion matrix (pooled 5-fold stratified CV, n = {pr['n_total']})")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label("Trial count")
    fig.tight_layout()
    fig.savefig(out_dir/"Figure2_confusion_matrix.png", dpi=300)
    fig.savefig(out_dir/"Figure2_confusion_matrix.pdf"); plt.close(fig)

    fig, axes = plt.subplots(1,2, figsize=(11,4.8))
    _cm(axes[0], np.array(pr["confusion_matrix"]), labels, "a  Three MOS channels", True)
    im = _cm(axes[1], np.array(fu["primary"]["confusion_matrix_four"]), labels,
             "b  + BME680 humidity", False)
    fig.colorbar(im, ax=axes, fraction=0.024, pad=0.02).set_label("Trial count")
    fig.savefig(out_dir/"Figure3_humidity_fusion.png", dpi=300,
                bbox_inches="tight", facecolor="white")
    fig.savefig(out_dir/"Figure3_humidity_fusion.pdf",
                bbox_inches="tight", facecolor="white"); plt.close(fig)

    imp = pr["importances"]; order = sorted(imp, key=imp.get, reverse=True)
    vals = [imp[k] for k in order]
    fig, ax = plt.subplots(figsize=(5,3.5))
    bars = ax.bar([CHANNEL[k] for k in order], vals, color="#4C72B0")
    ax.set_ylabel("Gini importance")
    ax.set_title(f"Sensor channel importance (random forest, n = {pr['n_total']})")
    ax.set_ylim(0, max(vals)*1.2)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x()+bar.get_width()/2, v+0.01, f"{v:.3f}", ha="center", fontsize=9)
    plt.xticks(rotation=15, ha="right"); fig.tight_layout()
    fig.savefig(out_dir/"FigureS1_feature_importance.png", dpi=300); plt.close(fig)

    al = [DISPLAY[c] for c in ab["classes"]]
    fig, axes = plt.subplots(1,2, figsize=(11.5,4.8))
    _cm(axes[0], np.array(ab["raw"]["confusion_matrix"]), al,
        "a  Raw divider voltage", True, 35)
    im = _cm(axes[1], np.array(ab["norm"]["confusion_matrix"]), al,
             "b  Rs/R0 normalized", False, 35)
    fig.colorbar(im, ax=axes, fraction=0.024, pad=0.02).set_label("Trial count")
    fig.savefig(out_dir/"FigureS2_normalization_ablation.png", dpi=300,
                bbox_inches="tight", facecolor="white"); plt.close(fig)
    print(f"Figures written to {out_dir}")


def write_tables(pr, ab, fu, cls, out_dir):
    classes = pr["classes"]
    pd.DataFrame([{"Analyte":DISPLAY[c],
                   "Support (n)":int(pr["per_class"][c]["support"]),
                   "Precision":round(pr["per_class"][c]["precision"],3),
                   "Recall":round(pr["per_class"][c]["recall"],3)}
                  for c in classes]).to_csv(out_dir/"TableII_per_class_primary.csv", index=False)

    pd.DataFrame([{"Features":"Raw divider voltage" if k=="raw" else "Rs/R0 normalized",
                   "Accuracy (%)":f"{ab[k]['accuracy_mean']*100:.1f} +/- {ab[k]['accuracy_std']*100:.1f}",
                   "Macro F1":round(ab[k]["macro_f1"],3),
                   "Glycerol F1":round(ab[k]["glycerol_f1"],3),
                   "Water F1":round(ab[k]["water_f1"],3),
                   "Other seven mean recall":round(ab[k]["other_seven_mean_recall"],3)}
                  for k in ("raw","norm")]).to_csv(out_dir/"TableI_normalization.csv", index=False)

    pd.DataFrame([{"Classifier":k,
                   "Accuracy (%)":f"{v['accuracy_mean']*100:.1f} +/- {v['accuracy_std']*100:.1f}",
                   "Macro F1":round(v["macro_f1"],3)}
                  for k,v in cls.items()]).to_csv(out_dir/"TableS1_classifiers.csv", index=False)

    pd.DataFrame([{"Analyte":DISPLAY[c], "n":ab["raw"]["support"][c],
                   "Raw F1":round(ab["raw"]["per_class_f1"][c],3),
                   "Rs/R0 F1":round(ab["norm"]["per_class_f1"][c],3)}
                  for c in ab["classes"]]).to_csv(out_dir/"TableS2_ablation_per_class.csv", index=False)

    fp = fu["primary"]["per_class"]
    pd.DataFrame([{"Analyte":DISPLAY[c], "n":int(fp[c]["support"]),
                   "Precision":round(fp[c]["precision"],3),
                   "Recall":round(fp[c]["recall"],3)}
                  for c in classes]).to_csv(out_dir/"TableS3_humidity_fusion.csv", index=False)
    print(f"Tables written to {out_dir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("../data"))
    ap.add_argument("--out-dir", type=Path, default=Path("../figures"))
    ap.add_argument("--permutations", type=int, default=200)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    primary = load_primary(args.data_dir)
    ablation = load_ablation(args.data_dir)
    integ = {"primary": integrity(primary, "Primary dataset", MQ),
             "ablation": integrity(ablation, "Ablation dataset", MQ)}
    pr  = analyse_primary(primary, args.permutations)
    cls = compare_classifiers(primary)
    ab  = analyse_ablation(ablation)
    fu  = analyse_fusion(primary, ablation)
    make_figures(pr, ab, fu, args.out_dir)
    write_tables(pr, ab, fu, cls, args.out_dir)
    with open(args.out_dir/"results_summary.json","w") as fh:
        json.dump({"integrity":integ,"primary":pr,"classifier_comparison":cls,
                   "ablation":ab,"humidity_fusion":fu}, fh, indent=2)
    print(f"Results JSON written to {args.out_dir/'results_summary.json'}")


if __name__ == "__main__":
    main()