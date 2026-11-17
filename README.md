# ChinaMDD

Code for comparing depression among Chinese adults aged 50 years and older between model-based estimates from the Global Burden of Disease Study 2023 (GBD 2023) and six waves of the China Health and Retirement Longitudinal Study (CHARLS, 2011 to 2021–2023): age and sex structure, time trends, the level of prevalence, and the number of people affected to 2035.

## Structure

```
ChinaMDD/
├── analysis/
│   └── code/
│       ├── 00_build_charls_panel.py     # harmonise six CHARLS waves into one person-wave panel
│       ├── 01_run_analysis.py           # all analyses, figures, tables, legends, source data and QC
│       ├── 02_build_tables_docx.py      # three-line DOCX tables from the table CSVs, checked cell by cell
│       ├── 03_export_charls_folder.py   # documented export of the processed CHARLS mental-health data
│       └── 04_charls_flow_diagram.py    # sample-derivation flow diagram and data-quality tables
├── data/
│   ├── raw/          # input data (not included; see data/raw/README.md)
│   └── processed/    # written by 00_build_charls_panel.py
├── requirements.txt
└── README.md
```

## Data

The data are not included. CHARLS microdata are available to registered users from the CHARLS website; GBD 2023 estimates from the GBD Results Tool; population projections from UN World Population Prospects 2024. File names and folder layout are listed in `data/raw/README.md`.

## Running

Python 3.10.

```bash
pip install -r requirements.txt
cd analysis/code
python3 00_build_charls_panel.py      # CHARLS .dta -> data/processed/charls_panel_2011_2023.csv
python3 01_run_analysis.py            # analyses, figures, tables, legends, source data, QC
python3 02_build_tables_docx.py       # DOCX tables
python3 03_export_charls_folder.py    # optional: processed-data export -> output/CHARLS/
python3 04_charls_flow_diagram.py     # optional: flow diagram -> output/CHARLS/
```

`01_run_analysis.py` writes its outputs next to the code folder:

| Folder (under `analysis/`) | Content |
|---|---|
| `02_Figures/` | main figures (PNG 300 dpi and PDF) |
| `03_Figure_Legends.md` | figure legends with the numbers filled in |
| `04_Tables/` | main tables (CSV, Markdown; DOCX from `02_build_tables_docx.py`) |
| `05_Supplementary_Figures/` | supplementary figures |
| `06_Supplementary_Tables/` | supplementary tables (CSV and one workbook) |
| `07_SourceData/` | source data for every figure (one workbook per figure, one sheet per panel) |
| `08_Results_summary.md` | results summary |
| `code/qc/` | quality-control checks |

Random draws use a fixed seed, so the outputs are reproducible.

## Methods in brief

- CHARLS: respondents aged ≥50 years with all ten CES-D-10 items and a cross-sectional weight; case definitions from symptom thresholds (CES-D-10 ≥10, ≥12, ≥15) to persistence, functional limitation and reported diagnosis.
- Survey-weighted prevalence with Taylor linearization (communities as primary sampling units); age-standardized rates with a fixed GBD 2020 standard; estimates pooled across waves are linearized jointly across waves.
- Numbers of people, projections (UN WPP 2024), Shapley decomposition and Rogan–Gladen tipping-point curves with a design-based community bootstrap (2,000 replicates).
- GBD uncertainty from lognormal draws matched to the published 95% uncertainty intervals.
