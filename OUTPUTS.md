# Analysis outputs

All paths below are relative to `--output-dir` (default `results/`). Figure numbering matches the manuscript. Source-data files contain unformatted estimates and the intervals used in the figures; CSV files include a `panel` column and XLSX files have separate worksheets by panel.

| Location | Contents |
|---|---|
| `processed/` | CHARLS person-wave panel, variable crosswalk, panel documentation and sample counts |
| `02_Figures/` | Main figures, PNG at 300 dpi and PDF |
| `04_Tables/` | Tables 1–3 in CSV and Markdown, plus `table_titles_notes.csv` |
| `05_Supplementary_Figures/` | Supplementary figures, PNG and PDF |
| `06_Supplementary_Tables/` | Supplementary CSV tables, a combined workbook, CHARLS cell estimates and aggregated GBD estimates |
| `07_SourceData/` | Figure source data as CSV and XLSX |
| `diagnostics/` | Numerical method identities, estimator comparisons and Taylor/bootstrap SE comparisons |
| `CHARLS/` | Optional local microdata exports, codebook, descriptive summaries and sample-flow outputs |

| Figure | File stem | Source-data stem |
|---|---|---|
| 1 | `Fig1_age_specific_prevalence_GBD_vs_CHARLS` | `Fig1_SourceData` |
| 2 | `Fig2_sex_ratio_by_age` | `Fig2_SourceData` |
| 3 | `Fig3_age_standardised_trend_2011_2023` | `Fig3_SourceData` |
| 4 | `Fig4_numbers_2011_2035` | `Fig4_SourceData` |
| 5 | `Fig5_decomposition` | `Fig5_SourceData` |
| 6 | `Fig6_tipping_point_Se_Sp` | `Fig6_SourceData` |

Supplementary figures use `SuppFig1`–`SuppFig7` prefixes. The CHARLS flow diagram is a separate descriptive output. Table 1 describes the survey sample, Table 2 gives age-standardized prevalence by definition and wave, and Table 3 gives population planning bases for 2023 and 2035. Captions and manuscript text are maintained with the manuscript.
