#!/usr/bin/env python3
"""Export the processed CHARLS mental-health data into MDD+Charle/CHARLS/ (self-contained, documented copy).

Run:    python3 03_export_charls_folder.py      (after 00_build_charls_panel.py)
Input:  ../../data/processed/charls_panel_2011_2023.csv, charls_variable_crosswalk.csv
Output: ../../../CHARLS/
          01_charls_mental_health_panel_2011_2023.csv     all person-waves (18+), mental-health + covariate columns
          02_charls_analytic_50plus_with_definitions.csv  analytic sample used in MS1 (≥50 y, CES-D complete, weighted) + D1–D7
          03_summary_by_wave_sex.csv                       weighted prevalence of each definition by wave × sex
          04_summary_by_wave_sex_age.csv                   same by 5-year age group
          05_codebook.csv                                  column-level codebook of file 01/02
          06_variable_crosswalk_by_wave.csv                raw CHARLS variable → harmonised variable, per wave
          README.md
          code/00_build_charls_panel.py                    copy of the build script (provenance)
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MS = HERE.parent.parent
OUT = MS / "output" / "CHARLS"
(OUT / "code").mkdir(parents=True, exist_ok=True)
PROC = MS / "data" / "processed"

P = pd.read_csv(PROC / "charls_panel_2011_2023.csv", low_memory=False)
WLAB = {2011: "2011", 2013: "2013", 2015: "2015", 2018: "2018", 2020: "2020", 2026: "2021–2023"}
AGES = ["50–54", "55–59", "60–64", "65–69", "70–74", "75–79", "80–84", "85+"]

# ----------------------------------------------------------------------------- file 01: full panel, ordered columns
cols = ["ID", "communityID", "wave", "wave_label", "iyear", "imonth", "age", "byear", "bmonth", "byear_wave", "bmonth_wave", "xrage_charls",
        "sex", "sex_wave", "weight", "weight_post", "crosssection", "died", "proxy",
        "hukou_agri", "urban_nbs",
        "cesd_bothered", "cesd_mind", "cesd_depressed", "cesd_effort", "cesd_hopeful", "cesd_fearful", "cesd_sleep", "cesd_happy",
        "cesd_lonely", "cesd_getgoing", "cesd_nmiss", "cesd10", "cesd10_prorated", "cesd6_nonsomatic", "cesd8_negative", "cesd10_prev", "wave_prev",
        "d4_persistent", "d4_any_prev", "dx_emot", "dx_emot_ever", "psy_treat", "adl_any", "srh_poor"]
P1 = P[cols].copy()
P1.to_csv(OUT / "01_charls_mental_health_panel_2011_2023.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------- file 02: analytic sample with definitions
A = P1[(P1.age >= 50) & P1.sex.isin([1, 2]) & P1.weight.notna() & P1.cesd10.notna() & (P1.crosssection == 1)].copy()
A["agegrp"] = pd.cut(A.age, bins=[50, 55, 60, 65, 70, 75, 80, 85, 200], right=False, labels=AGES)
A["D1_cesd10_ge10"] = (A.cesd10 >= 10).astype(int)
A["D2_cesd10_ge12"] = (A.cesd10 >= 12).astype(int)
A["D3_cesd10_ge15"] = (A.cesd10 >= 15).astype(int)
A["D4_persistent"] = A["d4_persistent"]
A["D5_ge10_with_ADL"] = np.where(A.adl_any.isna(), np.nan, ((A.cesd10 >= 10) & (A.adl_any == 1)).astype(float))
A["D6_self_reported_dx"] = A["dx_emot_ever"]
A["D7_ge10_without_dx"] = np.where(A.dx_emot_ever.isna(), np.nan, ((A.cesd10 >= 10) & (A.dx_emot_ever == 0)).astype(float))
A["nonsomatic6_ge6"] = (A.cesd6_nonsomatic >= 6).astype(float).where(A.cesd6_nonsomatic.notna())
A["negative8_ge8"] = (A.cesd8_negative >= 8).astype(float).where(A.cesd8_negative.notna())
A.to_csv(OUT / "02_charls_analytic_50plus_with_definitions.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------- files 03/04: weighted summaries
DEFS = ["D1_cesd10_ge10", "D2_cesd10_ge12", "D3_cesd10_ge15", "D4_persistent", "D5_ge10_with_ADL", "D6_self_reported_dx",
        "D7_ge10_without_dx", "nonsomatic6_ge6", "negative8_ge8", "cesd10"]


def wsum(g):
    out = {"n_unweighted": len(g), "mean_age": np.average(g.age, weights=g.weight)}
    for c in DEFS:
        m = g[c].notna()
        out[c + ("_mean" if c == "cesd10" else "_pct")] = (np.average(g.loc[m, c], weights=g.loc[m, "weight"]) * (1 if c == "cesd10" else 100)) if m.sum() >= 20 else np.nan
        out[c + "_n"] = int(m.sum())
    return pd.Series(out)


SEX = {1: "Males", 2: "Females", 3: "Both sexes"}
rows = []
for w, g in A.groupby("wave"):
    for s in (1, 2, 3):
        gs = g if s == 3 else g[g.sex == s]
        rows.append(pd.concat([pd.Series({"wave": WLAB[w], "sex": SEX[s]}), wsum(gs)]))
pd.DataFrame(rows).to_csv(OUT / "03_summary_by_wave_sex.csv", index=False, encoding="utf-8-sig")
rows = []
for w, g in A.groupby("wave"):
    for s in (1, 2, 3):
        gs = g if s == 3 else g[g.sex == s]
        for a, ga in gs.groupby("agegrp", observed=True):
            rows.append(pd.concat([pd.Series({"wave": WLAB[w], "sex": SEX[s], "agegrp": a}), wsum(ga)]))
pd.DataFrame(rows).to_csv(OUT / "04_summary_by_wave_sex_age.csv", index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------- file 05: codebook
CB = [
    ("ID", "Person ID, 12 digits (2011 IDs converted: insert '0' after position 9)"),
    ("communityID", "Community ID (PSU for variance estimation)"),
    ("wave", "Survey wave code: 2011, 2013, 2015, 2018, 2020, 2026 (= 2021–2023 wave 6)"),
    ("wave_label", "Wave label"),
    ("iyear", "Interview year (2011/2012, 2013, 2015/2016, 2018, 2020, 2021/2022/2023)"),
    ("age", "Exact age at interview = iyear − byear − 1[imonth < bmonth], using the person-level birth year/month"),
    ("byear / bmonth", "Person-level birth year/month: most frequent value reported across waves (ties → latest wave). 2020's preloaded zrbirthyear is excluded because it is shifted +2 y for ~90% of respondents"),
    ("byear_wave / bmonth_wave", "Birth year/month as reported in that wave (2011 ba002; 2013 ba002/zba002; 2015–2018 ba002 actual else ba004_w3 ID card; 2020 ba003 actual only; W6 ba006 actual else ba004 ID card else zrbirthyear)"),
    ("xrage_charls", "CHARLS's own generated age (2020, W6) kept for reference; in 2020 it is 2 years too low for ~90% of respondents"),
    ("imonth", "Interview month"),
    ("sex", "1 = male, 2 = female; person-level (mode across waves). sex_wave = value recorded in that wave"),
    ("weight", "Cross-sectional individual weight with household and individual non-response adjustment"),
    ("weight_post", "W6 only: post-stratification weight (5-year age × sex); sensitivity use"),
    ("crosssection", "1 = member of the cross-sectional sample (weights defined); 2011 all 1"),
    ("died", "1 = recorded as died (Sample_Infor), else 0"),
    ("proxy", "1 = proxy interview; NaN where not recorded (2013, 2018)"),
    ("hukou_agri", "1 = agricultural hukou, 0 = non-agricultural/unified/none; carried across waves when not re-asked"),
    ("urban_nbs", "2011 only: community urban (1) / rural (0) by NBS classification"),
    ("cesd_<item>", "CES-D-10 item recoded 0–3 (1–4 → 0–3; 'hopeful' and 'happy' reversed). Items: bothered, mind (trouble concentrating), depressed, effort, hopeful, fearful, sleep, happy, lonely, getgoing"),
    ("cesd_nmiss", "Number of missing CES-D-10 items (0–10)"),
    ("cesd10", "CES-D-10 total score 0–30; missing if any item missing"),
    ("cesd10_prorated", "Mean of available items × 10 when ≤2 items missing (sensitivity)"),
    ("cesd6_nonsomatic", "Sum of six non-somatic items (bothered, depressed, hopeful, fearful, happy, lonely), 0–18"),
    ("cesd8_negative / negative8_ge8", "Sum of the eight negatively worded items (without the reversed items hopeful, happy), 0–24; File 02 flag = ≥8 (proportional threshold). Sensitivity for the anomalous behaviour of the two positive items in 2013 and 2020"),
    ("cesd10_prev / wave_prev", "CES-D-10 score and wave of the person's previous participation"),
    ("d4_persistent / D4_persistent", "1 if CES-D-10 ≥10 in this wave and in the immediately preceding wave; NaN if the person did not take part in the preceding wave"),
    ("dx_emot", "1 = told by a doctor of emotional, nervous or psychiatric problems, as recorded in that wave (follow-up waves combine preloaded record, verification and new report)"),
    ("dx_emot_ever / D6_self_reported_dx", "dx_emot carried forward within person: once reported, always 1 (lifetime 'ever' definition, as in Harmonized CHARLS r*psyche)"),
    ("d4_any_prev", "Like D4 but the previous wave need not be the immediately preceding one"),
    ("psy_treat", "1 = currently receiving psychiatric/psychological treatment or medication (2011–2018 only; NaN otherwise)"),
    ("adl_any", "1 = difficulty with any of dressing, bathing, eating, bed transfer, toileting. 2011–2018: the whole functional-limitation module was skipped for ~30% of (younger, healthier) respondents; skipped = 0"),
    ("srh_poor", "1 = self-rated health poor or very poor"),
    ("agegrp", "File 02: 5-year age group 50–54 … 85+"),
    ("D1_cesd10_ge10", "File 02: CES-D-10 ≥10"),
    ("D2_cesd10_ge12", "File 02: CES-D-10 ≥12"),
    ("D3_cesd10_ge15", "File 02: CES-D-10 ≥15"),
    ("D5_ge10_with_ADL", "File 02: CES-D-10 ≥10 and adl_any = 1"),
    ("D7_ge10_without_dx", "File 02: CES-D-10 ≥10 and dx_emot = 0"),
    ("nonsomatic6_ge6", "File 02: six non-somatic items ≥6 (proportional threshold)"),
]
pd.DataFrame(CB, columns=["column", "definition"]).to_csv(OUT / "05_codebook.csv", index=False, encoding="utf-8-sig")
shutil.copy(PROC / "charls_variable_crosswalk.csv", OUT / "06_variable_crosswalk_by_wave.csv")
shutil.copy(HERE / "00_build_charls_panel.py", OUT / "code" / "00_build_charls_panel.py")
shutil.copy(HERE / "03_export_charls_folder.py", OUT / "code" / "03_export_charls_folder.py")
shutil.copy(HERE / "04_charls_flow_diagram.py", OUT / "code" / "04_charls_flow_diagram.py")

# ----------------------------------------------------------------------------- README
n_wave = P1.groupby("wave_label").size()
n_an = A.groupby("wave_label").size()
s3 = pd.read_csv(OUT / "03_summary_by_wave_sex.csv")
s3b = s3[s3.sex == "Both sexes"][["wave", "n_unweighted", "D1_cesd10_ge10_pct", "D2_cesd10_ge12_pct", "D3_cesd10_ge15_pct", "D4_persistent_pct",
                                  "D5_ge10_with_ADL_pct", "D6_self_reported_dx_pct", "cesd10_mean"]].round(2)
md = f"""# CHARLS 2011–2023 mental-health (depression) data

> Exported by `code/03_export_charls_folder.py` from the processed panel; raw `.dta` files are in `data/raw/CHARLS/`, the cleaning script is `code/00_build_charls_panel.py`.

## Files

| File | Content | Rows |
|---|---|---:|
| `01_charls_mental_health_panel_2011_2023.csv` | Person-wave panel of all respondents in six waves (one row per person per wave): CES-D-10 items and total score, self-reported psychiatric diagnosis, treatment, ADL, self-rated health, age, sex, weight, PSU | {len(P1):,} |
| `02_charls_analytic_50plus_with_definitions.csv` | Analytic sample: aged ≥50 years, all ten CES-D items, cross-sectional weight; with case definitions D1–D7 and 5-year age group | {len(A):,} |
| `03_summary_by_wave_sex.csv` | Weighted prevalence of each definition by wave × sex | {len(s3):,} |
| `04_summary_by_wave_sex_age.csv` | As above, by 5-year age group | — |
| `05_codebook.csv` | Column-level codebook of files 01 and 02 | — |
| `06_variable_crosswalk_by_wave.csv` | Raw variables used in each wave (CES-D, age, diagnosis, ADL, self-rated health, hukou, treatment, weight) | 6 |
| `07_CHARLS_data_flow.pdf` / `.png` | Sample-derivation flow diagram by wave (respondents → answered CES-D → all ten items → aged ≥50 → weighted), with exclusions at each step | — |
| `07_CHARLS_data_flow_counts.csv` | All numbers shown in the flow diagram | 6 |
| `08_data_quality_by_wave.csv` | Data quality by wave: duplicate IDs, missing age/sex/weight, CES-D missingness patterns, score ranges, variable missingness, weight variation | 6 |
| `09_panel_participation.csv` | Number of waves per person; person-waves for which D4 is defined | — |
| `code/` | Cleaning, export and flow-diagram scripts (`00_build_charls_panel.py`, `03_export_charls_folder.py`, `04_charls_flow_diagram.py`) | — |

## Sample size

| Wave | Panel person-waves (file 01) | Analytic sample ≥50 years (file 02) |
|---|---:|---:|
""" + "\n".join(f"| {w} | {n_wave[w]:,} | {n_an.get(w, 0):,} |" for w in ["2011", "2013", "2015", "2018", "2020", "2021–2023"]) + f"""

## Case definitions

| Code | Definition | Column |
|---|---|---|
| D1 | CES-D-10 ≥10 (current depressive symptoms, conventional threshold) | `D1_cesd10_ge10` |
| D2 | CES-D-10 ≥12 | `D2_cesd10_ge12` |
| D3 | CES-D-10 ≥15 (moderate to severe) | `D3_cesd10_ge15` |
| D4 | ≥10 in two consecutive waves (persistent symptoms; defined from 2013) | `D4_persistent` |
| D5 | ≥10 with any ADL limitation | `D5_ge10_with_ADL` |
| D6 | Self-reported doctor's diagnosis of emotional or psychiatric problems (lifetime, carried forward: 1 once reported) | `D6_self_reported_dx` |
| D7 | ≥10 without D6 | `D7_ge10_without_dx` |
| C | CES-D-10 continuous score 0–30 | `cesd10` |

CES-D-10 items are aligned across waves by **content**: 2011–2018 `dc009–dc018`, 2020 `dc016–dc025`, sixth wave `dc051–dc060`; item 5 (hopeful about the future) and item 8 (happy) are reverse-scored; the total score requires all ten items (`cesd10_prorated` allows up to two missing items).

## Weighted prevalence (aged ≥50 years, both sexes, %)

{s3b.to_markdown(index=False)}

## Notes for users

1. **The sixth wave (2021–2023) has only 175 respondents aged 45–49 years (9 men)**; the refresher sample did not replenish the youngest ages, so file 02 and all summaries start at 50 years. For ages 45–49 use 2011–2020 (in file 01).
2. **ADL skip pattern**: in 2011–2018 the whole functional-limitation module (DB001–DB014) was not asked of about 30% of respondents, who were younger and healthier (CES-D ≥10 in only 13–19%); they are coded as having no limitation.
3. **Sixth wave fielded over three years**: each person keeps the record of the year given by `res_wave`; `iyear` is the actual interview year (68% in 2021). Match to annual data such as GBD by interview year.
4. **Self-reported diagnosis is lifetime**, not point prevalence; 2013/2015 combine preloaded records, confirmation and follow-up questions, and 2020 and the sixth wave combine new questions with "diagnosed at the previous wave" items.
5. **Weights**: cross-sectional individual weights (household and individual non-response adjusted); about 9% of the sixth wave (non-cross-sectional sample) have no weight and are not in file 02. Use `communityID` as the PSU for variance estimation.
6. **Treatment variable** (`psy_treat`) is available only in 2011–2018 and asked only of those reporting a diagnosis; the sample is small.
7. 2011 IDs are converted to 12 digits and link to later waves by `ID`.

## Regenerate

```bash
cd analysis/code
python3 00_build_charls_panel.py && python3 03_export_charls_folder.py && python3 04_charls_flow_diagram.py
```
"""
(OUT / "README.md").write_text(md, encoding="utf-8")
print(f"Exported to {OUT}")
for f in sorted(OUT.rglob("*")):
    if f.is_file():
        print(f"  {f.relative_to(OUT)}  {f.stat().st_size/1e6:.1f} MB")
