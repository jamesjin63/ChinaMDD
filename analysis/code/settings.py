"""Shared input and output paths and input integrity constraints."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CHINAMDD_DATA_DIR", REPO_ROOT / "data" / "raw")).expanduser().resolve()
OUTPUT_DIR = Path(os.environ.get("CHINAMDD_OUTPUT_DIR", REPO_ROOT / "results")).expanduser().resolve()
PROCESSED_DIR = OUTPUT_DIR / "processed"
PANEL = Path(os.environ.get("CHINAMDD_PANEL", PROCESSED_DIR / "charls_panel_2011_2023.csv")).expanduser().resolve()

CROSSWALK = PANEL.parent / "charls_variable_crosswalk.csv"


def overlaps(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    return a == b or a in b.parents or b in a.parents


if overlaps(DATA_DIR, OUTPUT_DIR):
    raise ValueError("Input and output directories must be separate and must not contain one another.")
if "CHINAMDD_PANEL" in os.environ and overlaps(PANEL, OUTPUT_DIR):
    raise ValueError("An externally supplied panel must be outside the output directory.")


def require_files(paths):
    missing = [str(p) for p in paths if not Path(p).is_file()]
    if missing:
        raise FileNotFoundError("Missing required input files:\n" + "\n".join(missing)
                                + "\nSee data/raw/README.md for data sources and file layout.")


def charls_files(raw):
    """Return the exact, case-sensitive module paths read by the panel builder."""
    modules = {
        2011: ["demographic_background.dta", "health_status_and_functioning.dta", "weight.dta", "psu.dta"],
        2013: ["Demographic_Background.dta", "Health_Status_and_Functioning.dta", "Weights.dta"],
        2015: ["Demographic_Background.dta", "Health_Status_and_Functioning.dta", "Weights.dta", "Sample_Infor.dta"],
        2018: ["Demographic_Background.dta", "Health_Status_and_Functioning.dta", "Cognition.dta", "Weights.dta", "Sample_Infor.dta"],
        2020: ["Demographic_Background.dta", "Health_Status_and_Functioning.dta", "Weights.dta", "Sample_Infor.dta"],
    }
    paths = [raw / f"CHARLS{wave}" / "raw_dta" / name for wave, names in modules.items() for name in names]
    base = raw / "CHARLS2026" / "raw_dta"
    paths += [base / str(y) / name for y in (2021, 2022, 2023)
              for name in ("Demographics.dta", "Cognition_Depression.dta", "Health_Status_and_Functioning.dta")]
    return paths + [base / "2023" / name for name in ("Sample_Infor.dta", "Weights.dta")]


def validate_panel(panel):
    import numpy as np

    required = {"ID", "communityID", "wave", "iyear", "age", "sex", "weight", "crosssection", "cesd10",
                "cesd10_prorated", "cesd6_nonsomatic", "cesd8_negative", "d4_persistent", "adl_any",
                "dx_emot_ever", "hukou_agri", "srh_poor", "proxy", "weight_post"}
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"Missing processed-panel columns: {sorted(missing)}")
    if panel.duplicated(["ID", "wave"]).any():
        raise ValueError("Duplicate person-wave keys in the processed CHARLS panel.")
    for key in ("ID", "communityID", "wave"):
        if panel[key].isna().any() or panel[key].astype(str).isin(["", "nan"]).any():
            raise ValueError(f"Missing processed-panel key: {key}")
    if set(panel.wave.unique()) != {2011, 2013, 2015, 2018, 2020, 2026}:
        raise ValueError("The panel must contain all six expected CHARLS waves.")
    if not panel.sex.dropna().isin([1, 2]).all():
        raise ValueError("Sex must use 1 (male), 2 (female), or missing.")
    weight = panel.weight.dropna()
    if not (np.isfinite(weight) & (weight > 0)).all():
        raise ValueError("Nonmissing survey weights must be finite and positive.")
    for col, maximum in (("cesd10", 30), ("cesd10_prorated", 30), ("cesd6_nonsomatic", 18), ("cesd8_negative", 24)):
        if not panel[col].dropna().between(0, maximum).all():
            raise ValueError(f"Invalid score range in {col}.")
