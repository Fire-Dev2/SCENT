# SCENT

Low-cost embedded electronic nose for volatile organic compound (VOC) headspace classification.

This repository contains the data, analysis code, and hardware files supporting the manuscript:

> Nambi, T., Bhimireddy, N. & McElroy, J. P. *A low-cost embedded electronic nose classifies nine chemical headspaces offline using an embedded random forest classifier.* (under review)

---

## What this is

SCENT is an $83 open-hardware electronic nose. Three MQ-series metal oxide semiconductor (MOS) gas sensors sit in a 3D-printed PETG chamber with active purge fluidics. Acquisition, feature extraction, and classification all run on a Raspberry Pi 5 with no network dependency.

Reported result: **89.8% ± 0.8%** accuracy across nine chemical headspaces (450 trials, 50 per analyte), 5-fold stratified cross-validation, against an 11.1% chance baseline.

---

## Reproducing the reported results

```bash
git clone https://github.com/Fire-Dev2/SCENT.git
cd SCENT
pip install -r requirements.txt
cd code
python scent_analysis.py --data-dir ../data --out-dir ../figures
```

This prints the cross-validation accuracy, macro F1, per-class precision/recall, and confusion matrix, and writes to `figures/`:

| Output | Corresponds to |
|---|---|
| `Figure2_confusion_matrix.png` / `.pdf` | Manuscript Figure 2 |
| `Figure3_feature_importance.png` / `.pdf` | Manuscript Figure 3 |
| `Table1_per_class_metrics.csv` | Manuscript Table 1 |
| `results_summary.json` | All reported metrics, machine-readable |

Runtime is a few seconds on a laptop. Results are deterministic (`random_state=42` throughout).

**Software versions used for the reported numbers:** Python 3.12.3, scikit-learn 1.8.0. Minor version differences in scikit-learn may shift accuracy in the third decimal place.

---

## Data

### File organisation

Nine analytes, two CSV files each, 18 files total in `data/`.

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

Total: 450 trials, 50 per analyte, balanced across all nine classes.

> **TO COMPLETE:** Describe what distinguishes Batch A from Batch B — were they acquired on different days, in different sessions, after separate sensor warm-up cycles, or was a single acquisition run split? This matters: the analysis script reports a batch holdout check (train on Batch A, test on Batch B, 86.7% accuracy), and how much that check demonstrates depends entirely on what separates the two batches. If they are independent sessions it is a meaningful robustness result; if it is one session split arbitrarily it is a weak check.

> **TO COMPLETE:** If the terms "Test 1 Data", "Test 2 Data", and "Test 3 Data" are used elsewhere in project records, map them onto these files here so the naming is unambiguous.

### Column format

Every trial CSV has one row per trial and the following columns:

| Column | Units | Description |
|---|---|---|
| `MQ3_V` | V | MQ-3 sensor divider output voltage (alcohol-sensitive) |
| `MQ9_V` | V | MQ-9 sensor divider output voltage (combustible gas / CO) |
| `MQ135_V` | V | MQ-135 sensor divider output voltage (air quality / NH₃) |
| `TVOC_ppb` | ppb | Total VOC, auxiliary sensor |
| `eCO2_ppm` | ppm | Equivalent CO₂, auxiliary sensor |
| `Temp_C` | °C | Ambient temperature at acquisition |
| `Humidity_pct` | % RH | Ambient relative humidity at acquisition |
| `Trial_ID` | — | Trial index within analyte |
| `Label` | — | Analyte name |

**Only `MQ3_V`, `MQ9_V`, and `MQ135_V` are used as classifier features.** The auxiliary and environmental columns are provided for transparency and reuse but are not inputs to the reported model.

### Important note on feature representation

The reported classification uses **raw divider voltage**, not resistance-ratio (Rs/R₀) normalized features. A per-trial clean-air baseline resistance was not captured alongside this analyte panel, so the standard Rs/R₀ normalization described in the manuscript Methods could not be applied to these data. This is stated explicitly in the manuscript so the accuracy is not mistaken for a normalized result.

### Data integrity

`scent_analysis.py` runs automatic checks before computing any metric: total trial count, per-class balance, exact duplicate detection, and per-batch signal spread. The spread check exists because a batch of genuinely independent trials should vary well above ADC quantisation; a near-zero spread indicates replicated or derived rows rather than independent measurements. All 18 files in this repository pass.

> **TO COMPLETE:** An earlier set of nine `*_80.csv` files existed with near-zero trial-to-trial variance (spread ≈ 0.001 V, versus ≈ 0.05 V here) and with glycerol and distilled water numerically identical to four decimal places. Those files were superseded by the ones in this repository and must not be deposited. If they exist anywhere in project records, delete them or label them clearly as derived/averaged so they are never mistaken for raw acquisition output.

---

## Hardware

> **TO COMPLETE:** The following are referenced by the manuscript but not yet in this repository.

- `hardware/chamber.stl` and `hardware/chamber.step` — sampling chamber CAD, modelled in Autodesk Fusion 360, printed in PETG
- `hardware/photos/` — photographs of the assembled device (needed for manuscript Figure 1)
- `hardware/wiring.md` or schematic — sensor-to-ADS1115-to-Pi wiring
- `hardware/bill_of_materials.csv` — see template below

### Bill of materials

The manuscript's headline claim is an $83 total component cost, so this table needs real per-item prices and sources.

> **TO COMPLETE:** Fill in quantity, supplier, and actual price paid for each row. Costs must sum to the figure claimed in the manuscript.

| Component | Qty | Supplier / part number | Unit cost | Notes |
|---|---|---|---|---|
| Raspberry Pi 5 | 1 | | | Compute module |
| ADS1115 16-bit ADC | 1 | | | I²C, provides analog input |
| MQ-3 gas sensor | 1 | | | Alcohol-sensitive |
| MQ-9 gas sensor | 1 | | | Combustible gas / CO |
| MQ-135 gas sensor | 1 | | | Air quality / NH₃ |
| Exhaust fan | 1 | | | Active purge |
| PETG filament | — | | | Chamber, per-print cost |
| Wiring, connectors, misc | — | | | |
| **Total** | | | **$83** | Must match manuscript |

---

## Firmware / acquisition

> **TO COMPLETE:** The acquisition code that runs on the Raspberry Pi (sensor sampling, baseline/exposure/purge phase timing, CSV logging) is not yet in this repository. Reviewers assessing reproducibility will look for it, since the trial protocol described in the manuscript Methods is implemented there.

Acquisition protocol per the manuscript: 30 s baseline stabilization, 60 s exposure, 120 s active purge recovery.

---

## Repository layout

```
SCENT/
├── code/
│   └── scent_analysis.py        # Preprocessing, RF training, 5-fold CV, figures
├── data/                        # 18 trial CSVs (450 trials, 9 analytes)
├── figures/                     # Generated outputs (created on first run)
├── hardware/                    # CAD, BOM, photos  [TO COMPLETE]
├── requirements.txt
├── LICENSE                      # MIT — applies to code
├── LICENSE-DATA                 # CC BY 4.0 — applies to data and hardware files
└── README.md
```

---

## Licensing

- **Code** (`code/`): MIT License — see `LICENSE`
- **Data** (`data/`) **and hardware files** (`hardware/`): Creative Commons Attribution 4.0 International (CC BY 4.0) — see `LICENSE-DATA`

Both permit reuse with attribution.

---

## Citation

> **TO COMPLETE:** Archive a tagged release to Zenodo and add the resulting DOI here, then cite that DOI in the manuscript's Data Availability statement. A bare GitHub URL is not a persistent identifier and can change or disappear; journals increasingly expect a DOI.
>
> Steps: push everything above → tag a release (`v1.0`) on GitHub → sign in to Zenodo with GitHub → enable the SCENT repository under Zenodo's GitHub settings → create the release. Zenodo mints the DOI automatically. Note that Zenodo only captures releases created *after* the integration is enabled, so enable it first.

```
[Zenodo DOI once minted]
```

---

## Contact

Tharun Nambi — tharun.nambi@osumc.edu — ORCID [0009-0001-1177-6635](https://orcid.org/0009-0001-1177-6635)