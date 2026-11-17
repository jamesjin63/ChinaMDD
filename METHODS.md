# Methods implemented in the code

## Population and definitions

The primary CHARLS sample comprises respondents aged at least 50 years with known sex, a cross-sectional individual weight and all ten CES-D-10 items. The sixth wave is coded `2026` to identify its release, but its interviews occurred in 2021–2023. The six-wave primary sample comprises 78,575 person-waves from 21,978 people.

CES-D items are harmonized by content and scored 0–3; hopeful and happy are reversed. D1, D2 and D3 use total-score thresholds of 10, 12 and 15. D4 requires scores of at least 10 in two adjacent survey waves. D5 combines D1 with difficulty in any of dressing, bathing, eating, transferring or toileting. In 2011–2018, respondents skipped out of the entire functional-limitation module are coded as having no limitation. D6 is a lifetime self-report of a doctor's diagnosis of emotional, nervous or psychiatric problems, carried forward after a positive report. D7 combines D1 with no such diagnosis among respondents with known diagnosis status.

Birth year, birth month and sex use the most frequent reported value across waves, with ties resolved by the latest report. The shifted 2020 preloaded birth year is excluded. Age is computed at interview, subtracting one year when the interview month precedes the birth month. The six-wave panel retains missing scores for incomplete item sets rather than imputing a complete-case score.

## Survey estimates and pooling

Prevalence uses cross-sectional weights adjusted for household and individual nonresponse. Taylor linearization treats community as the primary sampling unit and retains zero-contribution communities in domain variances. Proportion intervals use the logit scale. Age-standardized prevalence is the weighted sum over eight age groups (50–54 through 80–84 and 85+), using the GBD China 2020 population of both sexes as the fixed standard; its variance linearizes the complete standardized sum.

Age prevalence ratios and female-to-male ratios are computed within waves. Wave estimates are pooled with inverse-variance weights; the pooled variance combines their community-level influence contributions jointly across waves. Logistic age associations use survey-weighted IRLS and a community-clustered sandwich covariance. GBD age associations use weighted least squares on log prevalence. Separate-wave trend contrasts propagate the two wave variances without estimating cross-wave covariance.

## GBD and population inputs

GBD prevalence numbers and rates are matched by cause, sex, age and year. Population denominators are recovered as number divided by rate times 100,000. Ages 85–89, 90–94 and 95+ are combined into 85+ by summing numbers and populations. The comparator for the sixth CHARLS wave is the interview-year-weighted mixture of GBD 2021–2023. Its plotting position is the corresponding weighted interview year.

GBD uncertainty is approximated with 2,000 lognormal draws centered on each point estimate on the log scale; the log-scale SD is derived from the reported 95% uncertainty bounds. Age-specific cells are sampled independently. Published joint posterior draws are not available in these inputs.

WPP 2024 medium-variant populations are summed into the same age groups and converted from thousands to people. Populations are fixed when propagating uncertainty.

## Counts, scenarios and decomposition

The random seed is `20261112`. CHARLS uncertainty for counts, scenarios, decomposition and tipping points uses 2,000 bootstrap replicates: within each wave, draw n−1 communities with replacement, with Rao–Wu rescaling. Each replicate recomputes all age–sex prevalences and derived quantities. Replicates are paired with GBD draws under independence between sources. These bootstrap draws are independent between survey waves; joint cross-wave linearization applies to the pooled Taylor estimates described above.

The 2023 planning bases apply sixth-wave CHARLS rates to GBD 2023 populations. Constant-rate scenarios apply the same rates to WPP 2035 populations. Trend-continued scenarios extrapolate age–sex logit trends, refitting them in each bootstrap replicate. They are demographic scenarios and bounds, rather than forecasts of clinical risk. Changes from 2023 to 2035 use WPP populations at both endpoints, so they do not equal a direct percentage change between count columns that use different population series.

The three-factor Shapley decomposition averages contributions over all six orders of changing population size, age–sex structure and prevalence rates. The ageing share is the structure contribution divided by total change and is not reported when total change is less than 10% of the baseline count.

## Tipping points and sensitivity analyses

Rogan–Gladen tipping curves solve for specificity at a range of assumed sensitivities that would align CHARLS apparent prevalence with GBD prevalence. They do not estimate diagnostic accuracy or a corrected clinical prevalence. CES-D-10 symptoms and diagnostic MDD represent distinct constructs.

Sensitivity analyses include six non-somatic items (threshold 6), eight negatively worded items (threshold 8), full-scale thresholds 8 and 16, prorating up to two missing items using the expanded eligible sample, unweighted estimates, exclusion of recorded proxy interviews and sixth-wave post-stratification weights. Missing proxy status in 2013 and 2018 remains unavailable. Numerical diagnostics compare equivalent estimators and uncertainty approximations and check decomposition identities.
