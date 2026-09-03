# SCENT

Low-cost embedded electronic nose for volatile organic compound (VOC) headspace classification.

Data and analysis code supporting:

> Nambi, T., Bhimireddy, N. & McElroy, J. P. *Resistance-ratio normalization does not resolve humidity-limited confusion in a three-sensor offline electronic nose.* (under review)

---

## What this is

SCENT is an $83 open-hardware electronic nose. Three MQ-series metal oxide semiconductor (MOS) gas sensors sit in a 3D-printed PETG chamber with active purge fluidics. Acquisition, feature extraction, and classification all run on a Raspberry Pi 5 with no network dependency. A BME680 and a CCS811 are logged alongside the array.

Three results:

| | |
|---|---|
| Three MQ channels, nine headspaces | **89.8 ± 0.8%** accuracy (chance 11.1%) |
| Adding Rs/R0 normalization | **80.0 ± 1.5%** — no significant change (McNemar p = 0.076) |
| Adding BME680 relative humidity | **99.6 ± 0.5%** (McNemar p < 0.001) |

The residual glycerol/water confusion under the three MQ channels is physical, not a signal-conditioning artifact: both headspaces are water-dominated at ambient temperature. Resistance-ratio referencing does not resolve it; a humidity transducer does.

---

## Repository contents

```
SCENT/
├── Test 3 Data/                          # primary dataset, 450 trials (18 CSVs)
├── SCENT_baseline_normalization_trials/  # ablation dataset, 245 trials
├── Scent analysis                        # analysis script (Python)
├── Requirements.txt                      # package versions
├── License                               # MIT — code
├── Data License                          # CC BY 4.0 — data
└── README.md
```

---

## Running the analysis

The script reads all trial CSVs from a single directory. The two datasets currently live in separate folders, so copy them into one directory first:

```bash
git clone https://github.com/Fire-Dev2/SCENT.git
cd SCENT
pip install -r Requirements.txt

mkdir -p data figures
cp "Test 3 Data"/*.csv data/
cp SCENT_baseline_normalization_trials/*.csv data/

python "Scent analysis" --data-dir data --out-dir figures
```

Runtime is a few minutes, dominated by the label-permutation test; pass `--permutations 60` to shorten it. All results are deterministic under a fixed seed (`random_state=42`).

**Outputs written to `figures/`:**

| Output | Corresponds to |
|---|---|
| `Figure2_confusion_matrix.png` / `.pdf` | Manuscript Fig. 2 |
| `Figure3_humidity_fusion.png` / `.pdf` | Manuscript Fig. 3 |
| `FigureS1_feature_importance.png` | Supplementary Fig. S1 |
| `FigureS2_normalization_ablation.png` | Supplementary Fig. S2 |
| `TableI_normalization.csv` | Manuscript Table I |
| `TableII_per_class_primary.csv` | Manuscript Table II |
| `TableS1_classifiers.csv` | Supplementary Table S1 |
| `TableS2_ablation_per_class.csv` | Supplementary Table S2 |
| `TableS3_humidity_fusion.csv` | Supplementary Table S3 |
| `results_summary.json` | Every reported statistic, machine-readable |

The script also prints the exact binomial and permutation tests against chance, the McNemar and paired-t tests on the normalization ablation, the batch and cross-day holdouts, the seven-classifier comparison, and the per-analyte mean humidity that underpins the physical explanation.

**Versions used for the reported numbers:** Python 3.12.3, scikit-learn 1.8.0, statsmodels, scipy, numpy, pandas, matplotlib. Minor scikit-learn version differences may shift accuracy in the third decimal place.

---

## Data

### Primary dataset — 450 trials

In `Test 3 Data/`. Nine analytes, 50 trials each, acquired in two batches per analyte (40 and 10 trials) **on separate days**. Trial order was randomized and interleaved across analytes rather than blocked, so within-session baseline drift is distributed across classes rather than confounded with class identity.

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

The `_80` / `_20` suffixes refer to the trial split, not to concentration. All analytes were used undiluted as purchased.

### Ablation dataset — 245 trials

In `SCENT_baseline_normalization_trials/`, file `New_Protocol_Dataset.csv`. Same nine analytes under a modified protocol in which the **clean-air baseline resistance R₀ of each channel was recorded immediately before every exposure**, permitting resistance-ratio features to be computed per trial. Acquired over two days (`Batch_Day` column): 35 trials each for glycerol and distilled water, the pair responsible for the dominant error mode, and 25 for each of the other seven.

This dataset supports the normalization ablation and the humidity-fusion result. It is a separate acquisition from the primary dataset, so the headline three-channel accuracy and the raw-versus-normalized comparison are **not matched trial-for-trial** — stated as a limitation in the manuscript.

### Column format

| Column | Units | Description |
|---|---|---|
| `MQ3_V` | V | MQ-3 divider output (alcohol-sensitive) |
| `MQ9_V` | V | MQ-9 divider output (combustible aliphatics, CO) |
| `MQ135_V` | V | MQ-135 divider output (air quality, NH₃) |
| `MQ3_R0`, `MQ9_R0`, `MQ135_R0` | load-resistor units | Per-trial clean-air baseline resistance (ablation dataset only) |
| `TVOC_ppb` | ppb | Total VOC, CCS811 |
| `eCO2_ppm` | ppm | Equivalent CO₂, CCS811 |
| `Temp_C` | °C | Ambient temperature, BME680 |
| `Humidity_pct` | % RH | Ambient relative humidity, BME680 |
| `Trial_ID` | — | Trial index within analyte |
| `Batch_Day` | — | Acquisition day (ablation dataset only) |
| `Label` | — | Analyte name |

**Which columns are classifier inputs:** the three MQ voltages for the primary result; those three plus `Humidity_pct` for the fusion result; `Rs/R0` derived from the MQ voltages and the R₀ columns for the ablation. `TVOC_ppb`, `eCO2_ppm`, and `Temp_C` are logged for transparency and are not used by any reported model.

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

- **Code**: MIT — see `License`
- **Data**: CC BY 4.0 — see `Data License`

Both permit reuse with attribution.

---

## Citation

Please cite the manuscript. The repository is referenced in the paper as:

```
https://github.com/Fire-Dev2/SCENT
```

Tagged releases are listed under Releases; `v4` is current.

---

## Contact

Tharun Nambi — tharun.nambi@osumc.edu — ORCID [0009-0001-1177-6635](https://orcid.org/0009-0001-1177-6635)
