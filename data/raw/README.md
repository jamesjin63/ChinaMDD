# Research inputs

Inputs are not redistributed. The directory selected by `--data-dir` is this raw-input root, not its parent. File discovery is limited to the exact paths below; filenames and capitalization are significant.

## Sources and releases

| Input | Source and access | Version |
|---|---|---|
| CHARLS | [CHARLS](https://charls.pku.edu.cn/), registration and provider terms apply | 2011, 2013, 2015, 2018, 2020, and the 2021–2023 sixth wave, release 20261110 |
| GBD | [GBD Results Tool](https://vizhub.healthdata.org/gbd-results/) | GBD 2023 |
| Population | [UN World Population Prospects](https://population.un.org/wpp/) | WPP 2024, medium variant |

The CHARLS release identifier is not an interview year. Original download dates are not recorded in this code package.

## CHARLS module layout

Under `CHARLS/<folder>/raw_dta/`, supply:

| Folder | Required files |
|---|---|
| `CHARLS2011` | `demographic_background.dta`, `health_status_and_functioning.dta`, `weight.dta`, `psu.dta` |
| `CHARLS2013` | `Demographic_Background.dta`, `Health_Status_and_Functioning.dta`, `Weights.dta` |
| `CHARLS2015` | `Demographic_Background.dta`, `Health_Status_and_Functioning.dta`, `Weights.dta`, `Sample_Infor.dta` |
| `CHARLS2018` | `Demographic_Background.dta`, `Health_Status_and_Functioning.dta`, `Cognition.dta`, `Weights.dta`, `Sample_Infor.dta` |
| `CHARLS2020` | `Demographic_Background.dta`, `Health_Status_and_Functioning.dta`, `Weights.dta`, `Sample_Infor.dta` |
| `CHARLS2026` | In each of `2021/`, `2022/`, `2023/`: `Demographics.dta`, `Cognition_Depression.dta`, `Health_Status_and_Functioning.dta`; additionally `2023/Sample_Infor.dta` and `2023/Weights.dta` |

Modules join on respondent `ID`; the 2011 PSU module joins on `communityID`. Each module must have one row per join key. IDs remain strings; 2011 IDs are expanded to the 12-digit format before linking waves. For the sixth wave, the builder stacks the three file-years and retains each respondent's `res_wave` response-year record. It does not search other folders or automatically select newer releases.

CES-D-10 raw items are `dc009`–`dc018` in 2011–2018, `dc016`–`dc025` in 2020 and `dc051`–`dc060` in the sixth wave. Responses 1–4 are scored 0–3; hopeful and happy are reversed. Cross-sectional weights use `ind_weight_ad2` in 2011 and `INDV_weight_ad2` thereafter; `INDV_weight_post2` is the sixth-wave sensitivity weight. Raw sex values are 1 (male) and 2 (female). Interview timing comes from `iyear`/`imonth`, supplemented by sample information. Birth-date, diagnosis, ADL, hukou, self-rated-health and treatment mappings are specified in the dictionaries and builder functions in `analysis/code/00_build_charls_panel.py`; the executable conversion exports these mappings as `charls_variable_crosswalk.csv`.

Convert the original Stata modules to the analysis-ready panel:

```bash
python run.py --prepare-only --data-dir /path/to/raw_inputs --output-dir /path/to/results
```

This creates `processed/charls_panel_2011_2023.csv`, the variable crosswalk, panel documentation and sample counts under the chosen output directory. Missing or duplicate input keys stop preparation. Variables unavailable in particular waves remain missing; age and sex harmonization, diagnosis carry-forward and ADL skip rules are described in [METHODS.md](../../METHODS.md).

## GBD estimates

File: `GBD2023/China_mental_disorders_GBD2023_1990_2023.csv` (CSV).

Required columns: `location_id`, `measure_id`, `cause_id`, `sex_id`, `age_id`, `year`, `metric_id`, `val`, `lower`, `upper`. Unique key: location × measure × cause × sex × age × year × metric. Bounds and estimates must be finite, nonnegative and ordered.

Export China only (`location_id=6`), prevalence (`measure_id=5`), causes 558 (mental disorders), 567 (depressive disorders), 568 (MDD) and 571 (anxiety disorders), sexes 1 (male), 2 (female), 3 (both), years 1990–2023, and both number (`metric_id=1`, people) and rate (`metric_id=3`, per 100,000). The analysis retains 2011–2023 and age IDs 15, 16, 17, 18, 19, 20, 30, 31, 32 and 235 (50–54 through 95+). Exporting ages 45+ is acceptable; younger ages are filtered out. Number and rate rows must match. Ages 85–89, 90–94 and 95+ are combined into 85+.

## WPP population

File: `WPP2024/WPP2024_PopulationByAge5GroupSex_Medium.csv.gz` (gzip-compressed CSV).

Required columns: `Location`, `Variant`, `Time`, `AgeGrpStart`, `PopMale`, `PopFemale`, `PopTotal`. The analysis selects `Location="China"`, `Variant="Medium"`, years 2011–2035 and ages starting at 50 or older. For the selected location and variant, year × five-year age-group start is unique. Populations are in thousands and must be finite and nonnegative; the analysis multiplies them by 1,000 to obtain people. Supply all age groups through the oldest open age group in each selected year.

## Reusing a processed panel

`--panel` requires a CSV produced by the panel builder and its sibling `charls_variable_crosswalk.csv`. The unique key is `ID` × `wave`; codes are 2011, 2013, 2015, 2018, 2020 and 2026. Retain all builder columns, including identifiers, interview timing, age, sex, weights, individual CES-D items and scores, missing-item count, ADL, diagnosis, persistence, hukou, self-rated health and proxy status. Scores use 0–30 (ten items and prorated score), 0–18 (six non-somatic items) and 0–24 (eight negative items); binary derived variables use 0/1 with missing values where undefined. Nonmissing survey weights must be positive and finite. The primary analysis filters age ≥50, known sex, complete ten-item scores, a weight and `crosssection=1`; the prorating sensitivity uses its expanded eligible sample.

GBD and WPP inputs are still read from `--data-dir` when reusing a panel. No research input or local respondent-level export should be added to the repository or source archive.
