# SCENT

Low-cost embedded electronic nose for volatile organic compound (VOC) headspace classification.

Data, acquisition code, and analysis code supporting:

> Nambi, T., Bhimireddy, N. & McElroy, J. P. *Isolating the contributions of
> resistance-ratio normalization and humidity fusion in a low-cost three-sensor
> offline electronic nose.* Manuscript sensors-4609768, under revision at *Sensors*.

---

## What this is

SCENT is an $83 open-hardware electronic nose. Three MQ-series metal oxide semiconductor (MOS) gas sensors sit in a 3D-printed PETG chamber with active purge fluidics. Acquisition, feature extraction, and classification all run on a Raspberry Pi 5 with no network dependency.

The chamber STL and the Fritzing wiring sketch are in [`hardware/`](hardware/).

Three results. Every figure below is the **mean ± SD across ten random seeds**,
each seed shared by the fold splitter and the forest, with the observed range in
brackets. Earlier versions of this README quoted a single seed's across-fold
spread, which is a different and smaller quantity.

| Feature set | Dataset | Accuracy |
|---|---|---|
| Three MQ channels | primary, n = 450 | **90.2 ± 0.5%** (89.3–90.9), chance 11.1% |
| Three MQ + BME680 relative humidity | primary, n = 450 | **99.3 ± 0.2%** (99.1–99.6) |
| Raw divider voltage | ablation, n = 245 | **86.2 ± 0.9%** (85.3–87.3) |
| Rs/R0 normalized | ablation, n = 245 | **82.4 ± 1.9%** (79.2–84.9) |

Humidity fusion is significant at every seed (McNemar p from 5.4×10⁻¹¹ to
6.8×10⁻⁹). Resistance-ratio normalization is not: across ten seeds McNemar p
ranges from 0.034 to 1.00, and only two of ten fall below 0.05. For the forest the 3.8-point drop
reaches trial-level significance at only two of ten seeds, but the same division
costs two linear classifiers 8-9 points, at eight and ten of ten seeds. The claim
is therefore **no benefit and a consistent cost**, not a neutral transform.

The residual glycerol/water confusion under the three MQ channels is physical, not a signal-conditioning artifact: both headspaces are water-dominated at ambient temperature. Resistance-ratio referencing does not resolve it; a humidity transducer does.

A leave-one-sensor-out ablation (`analysis/loso.py`) shows the array is not
minimal: differencing the full and reduced
models seed by seed, dropping **MQ-9** costs 0.89 ± 0.63 points on three channels,
with the two-channel model the more accurate at one of ten seeds, and −0.13 ± 0.16
points on four, where the reduced model is at least as accurate at every seed.
Dropping MQ-3 costs 8.58 ± 0.69 points and MQ-135 2.62 ± 0.63.

---

## Repository contents

```
SCENT/
├── data/                  # 18 per-analyte CSVs = 450-trial primary acquisition;
│                        # New_Protocol_Dataset.csv = 245-trial ablation acquisition
│                        # (file-by-file breakdown under "Data" below)
├── hardware/              # chamber STL, Fritzing wiring sketch, part list
├── analysis/
│   ├── seed_sweep.py      # ten-seed sweep over the four feature sets
│   ├── loso.py            # leave-one-sensor-out and single-channel ablation
│   ├── learning_curve.py  # held-out accuracy against training-set size
│   └── tvoc_checks.py     # exclusion evidence for the CCS811 channel
├── results/               # JSON output of each script above, plus the per-seed CSV
├── acquisition.py         # runs one trial on the Raspberry Pi
├── scent_analysis.py      # single-seed results and Figures 3–6
├── Requirements.txt
├── LICENSE                # MIT — code
├── LICENSE-DATA           # CC BY 4.0 — data
└── README.md
```

`figures/` is generated output and is not committed.

---

## Acquisition

`acquisition.py` runs one trial of the three-phase protocol on the Pi:

| Phase | Duration | |
|---|---|---|
| baseline | 30 s | clean-air stabilization before the sample is introduced |
| exposure | 60 s | sample headspace present |
| purge | 120 s | active exhaust, sensors returning to baseline |

```bash
python3 acquisition.py --trial 1 --scent ethanol --outdir data
```

All channels are sampled at **1 Hz** and each phase is reduced to the **arithmetic mean** of its samples, so one trial yields one value per channel per phase and the script writes one record per trial.

**The analyses in the manuscript use the exposure-phase columns.** The deposited datasets below carry those columns only, under the shorter names given in the column table.

Two implementation details the manuscript relies on:

- The CCS811 environmental compensation register (`ENV_DATA`, `0x05`) is never written, so the TVOC and eCO2 outputs are independent of the BME680 readings.
- `wait_ccs_ready()` polls the data-ready flag before every read, so logged values are never stale returns from a failed transaction.

Hardware: MQ-3, MQ-9, and MQ-135 read through an ADS1115 on A0/A1/A2; BME680 for temperature and relative humidity; CCS811 for eCO2 and TVOC. All on I²C.

---

## Reproducing the reported values

```bash
git clone https://github.com/Fire-Dev2/SCENT.git
cd SCENT
pip install -r Requirements.txt

python3 scent_analysis.py --data-dir data --out-dir figures   # single-seed results, Figures 3-6
python3 analysis/seed_sweep.py                                 # the reported mean +/- SD
python3 analysis/loso.py                                       # leave-one-sensor-out
python3 analysis/learning_curve.py                             # accuracy vs training-set size
python3 analysis/tvoc_checks.py                                # CCS811 exclusion evidence
```

The four scripts in `analysis/` default to `--data-dir data --out-dir results`
and need no arguments from the repository root.

`scent_analysis.py` takes a few minutes, dominated by the label-permutation
test; pass `--permutations 60` to shorten it. `seed_sweep.py` and `loso.py`
fit ten seeds each and take a few minutes more.

**On seeds.** `scent_analysis.py` is deterministic at `random_state=42`, but a
single seed is a reproducibility guarantee, not an uncertainty estimate. Seed 42
sits at the top of the ten-seed range for humidity fusion and at the bottom for
the normalized ablation, so it flatters one result and penalises the other. The
intervals quoted in this README and in the manuscript come from
`analysis/seed_sweep.py`, which is the number to compare against.

**Outputs written to `figures/`:**

| Output | Corresponds to |
|---|---|
| `Figure2_confusion_matrix.png` / `.pdf` | Manuscript Fig. 3 |
| `Figure3_humidity_fusion.png` / `.pdf` | Manuscript Fig. 6 |
| `FigureS1_feature_importance.png` | Manuscript Fig. 4 |
| `FigureS2_normalization_ablation.png` | Manuscript Fig. 5 |
| `TableI_normalization.csv` | Manuscript Table 3 |
| `TableII_per_class_primary.csv` | Manuscript Table 1 |
| `TableS1_classifiers.csv` | Manuscript Table 2 |
| `TableS2_ablation_per_class.csv` | Per-class ablation detail |
| `TableS3_humidity_fusion.csv` | Manuscript Table 4 |
| `results_summary.json` | Every single-seed statistic, machine-readable |

**Outputs written to `results/` by the scripts in `analysis/`:**

| Output | Corresponds to |
|---|---|
| `seed_sweep_results.json`, `seed_sweep_per_seed.csv` | Manuscript Table 8, the reported intervals |
| `loso_results.json` | Leave-one-sensor-out, Section 3.3 |
| `learning_curve_results.json` | Manuscript Fig. 9 |
| `tvoc_checks_results.json` | Supplementary Tables S1–S4 |

The script also prints the exact binomial and permutation tests against chance, the McNemar and paired-t tests on the normalization ablation, the batch and cross-day holdouts, the seven-classifier comparison, and the per-analyte mean humidity that underpins the physical explanation.

**Versions used for the reported numbers:** Python 3.12.3, scikit-learn 1.8.0, statsmodels, scipy, numpy, pandas, matplotlib. Minor scikit-learn version differences may shift accuracy in the third decimal place.

---

## Data

### Primary dataset — 450 trials

In `data/`. Nine analytes, 50 trials each, acquired in two batches per analyte (40 and 10 trials) **on separate days**. Trial order was randomized and interleaved across analytes rather than blocked, so within-session baseline drift is distributed across classes rather than confounded with class identity.

| Analyte | Batch A (40 trials) | Batch B (10 trials) |
|---|---|---|
| Acetone | `MQ-3_Sensor_Data_Acetone_80.csv` | `MQ-3_Sensor_Data_Acetone_20.csv` |
| Acetic acid | `Acetic_Acid_80_Data.csv` | `Acetic_Acid_20_Data.csv` |
| Ammonia | `MQ-3_Sensor_Data_Ammonia_80.csv` | `MQ-3_Sensor_Data_Ammonia_20.csv` |
| Distilled water | `MQ-3_Sensor_Data_Distilled_Water_80.csv` | `MQ-3_Sensor_Data_Distilled_Water_20.csv` |
| Ethanol | `Ethanol_80_Sensor_Data.csv` | `Ethanol_20_Sensor_Data.csv` |
| Ethyl acetate | `Ethyl_Acetate_80_Sensor_Data.csv` | `Ethyl_Acetate_20.csv` |
| Glycerol | `Glycerol_80_Data.csv` | `Glycerol_20_Sensor_Data.csv` |
| Hydrogen peroxide | `Hydrogen_Peroxide_80_Sensor_Data.csv` | `Hydrogen_Peroxide_20.csv` |
| Propylene glycol | `Propylene_Glycol_80_Data.csv` | `Propylene_Glycol_20_Sensor_Data.csv` |

The `_80` / `_20` suffixes refer to the trial split, not to concentration. All analytes were used undiluted as purchased, 5 mL per trial, equilibrated 30 min before sampling.

### Ablation dataset — 245 trials

In `data/New_Protocol_Dataset.csv`. Same nine analytes under a modified protocol in which the **clean-air baseline resistance R₀ of each channel was recorded immediately before every exposure**, permitting resistance-ratio features to be computed per trial. Acquired over two days (`Batch_Day` column): 35 trials each for glycerol and distilled water, the pair responsible for the dominant error mode, and 25 for each of the other seven.

This is a separate acquisition from the primary dataset, so the headline three-channel accuracy and the raw-versus-normalized comparison are **not matched trial-for-trial** — stated as a limitation in the manuscript.

### Column format

| Column | Units | Description |
|---|---|---|
| `MQ3_V` | V | MQ-3 divider output (alcohol-sensitive) |
| `MQ9_V` | V | MQ-9 divider output (combustible aliphatics, CO) |
| `MQ135_V` | V | MQ-135 divider output (air quality, NH₃) |
| `MQ3_R0`, `MQ9_R0`, `MQ135_R0` | load-resistor units | Per-trial clean-air baseline resistance (ablation dataset only) |
| `TVOC_ppb` | ppb | Total VOC, CCS811 — **excluded from all analyses, see below** |
| `eCO2_ppm` | ppm | Equivalent CO₂, CCS811 |
| `Temp_C` | °C | In-chamber temperature, BME680 |
| `Humidity_pct` | % RH | In-chamber relative humidity, BME680 |
| `Trial_ID` | — | Trial index within analyte |
| `Batch_Day` | — | Acquisition day (ablation dataset only) |
| `Label` | — | Analyte name |

Every value is the mean over the 60 s exposure phase, 60 samples per trial.

**Classifier inputs:** the three MQ voltages for the primary result; those three plus `Humidity_pct` for the fusion result; Rs/R0 derived from the MQ voltages and the R₀ columns for the ablation. `eCO2_ppm` and `Temp_C` are evaluated as alternative fourth features but are not part of the headline model.

### The TVOC column

`TVOC_ppb` is **excluded from every analysis** and is retained only for completeness. Across both datasets the nine analyte classes occupy strictly disjoint TVOC bands, with a minimum inter-class gap of +4.635 pooled standard deviations and no overlap in any of the 36 class pairs; every other channel has a negative minimum gap and overlapping pairs. Fitted alone the channel classifies all nine analytes at 100.0 ± 0.0%.

Acquisition-order artifacts, derivation from the MOS channels, environmental compensation, cached reads, and quantization have been excluded. The behavior is unexplained and is reported as such in the manuscript. Do not use this column.

### Feature definitions

Raw features are the divider voltages as logged. Resistance-ratio features are computed as

```
Rs/RL = (Vc / Vout) − 1        with Vc = 5 V
feature = (Rs/RL) / R0         per channel, per trial
```

R₀ is logged in load-resistor units, so RL cancels in the ratio.

### Data integrity

The analysis script runs automatic checks before computing any metric: trial counts, class balance, exact-duplicate detection, and per-analyte signal spread. The spread check exists because a batch of genuinely independent trials varies well above ADC quantisation; a near-zero spread indicates replicated or derived rows rather than independent measurements. Both datasets pass, and the check prints a warning naming any analyte that fails.

---

## Licensing

- **Code**: MIT — see `LICENSE`
- **Data**: CC BY 4.0 — see `LICENSE-DATA`

Both permit reuse with attribution.

---

## Citation

Please cite the manuscript. The repository is referenced in the paper as:

```
https://github.com/Fire-Dev2/SCENT
```

Tagged releases are listed under Releases.

---

## Contact

Tharun Nambi — tharun.nambi@osumc.edu — ORCID [0009-0001-1177-6635](https://orcid.org/0009-0001-1177-6635)
