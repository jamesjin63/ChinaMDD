# ChinaMDD

Research code for **Depression in Aging China: Comparing Global Estimates With National Survey Data**.

This repository compares age and sex patterns, prevalence trends, population counts and demographic scenarios among Chinese adults aged 50 years or older, using GBD 2023 estimates, six CHARLS waves (2011, 2013, 2015, 2018, 2020 and 2021–2023), and UN World Population Prospects 2024. CES-D-10 symptom definitions and GBD diagnostic estimates represent different constructs; the tipping-point analysis examines the assumptions needed to align their levels.

## Installation

Python 3.10 or later is required. Install the analysis dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```



## Data and running

Research inputs are not distributed. Obtain the data from the providers and follow the exact file layout in [data/raw/README.md](data/raw/README.md).

From the repository root:

```bash
python run.py
```

All generated files, including the processed panel, are written under `results/`. To select other locations:

```bash
python run.py --data-dir /path/to/raw_inputs --output-dir /path/to/results
```

The input and output directories must be separate and cannot contain each other. The complete command prepares the six-wave CHARLS panel and then runs the analyses. Missing inputs or a failed subprocess stop the command with a nonzero exit status.

Prepare the panel without fitting the analyses:

```bash
python run.py --prepare-only
```

Reuse a previously prepared panel, with `charls_variable_crosswalk.csv` alongside it:

```bash
python run.py --panel /path/to/processed/charls_panel_2011_2023.csv --output-dir /path/to/new_results
```

The external panel must be outside the new output directory. Raw GBD and WPP files remain required under `--data-dir`. To include optional local microdata exports, descriptive summaries and a sample-flow diagram:

```bash
python run.py --with-charls-export
```

These exports include respondent records and remain subject to the data providers' terms.

## Repository layout

```text
ChinaMDD/
├── run.py
├── requirements.txt
├── METHODS.md
├── OUTPUTS.md
├── analysis/code/
│   ├── settings.py
│   ├── 00_build_charls_panel.py
│   ├── 01_run_analysis.py
│   ├── 03_export_charls_folder.py
│   └── 04_charls_flow_diagram.py
└── data/raw/README.md
```

## Outputs and methods

The analysis exports six main figures and seven supplementary figures (PDF and PNG), main and supplementary tables, and figure source data (CSV and XLSX, one worksheet per panel). See [OUTPUTS.md](OUTPUTS.md) for filenames and locations.

Survey-weighted estimates use community-level Taylor linearization; pooled estimates account for communities shared across waves. Counts, demographic scenarios, decomposition and tipping-point analyses propagate uncertainty with 2,000 community bootstrap replicates and 2,000 GBD draws. The random seed is fixed at `20261112`. See [METHODS.md](METHODS.md) for definitions, assumptions and sensitivity analyses.
