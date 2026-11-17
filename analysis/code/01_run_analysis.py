#!/usr/bin/env python3
"""GBD 2023 vs CHARLS 2011–2023: depression among Chinese adults aged ≥50 — tables, figures, legends, source data, QC (MS1 V1).

Run:    python3 00_build_charls_panel.py  (once)  ->  python3 01_run_analysis.py  ->  python3 02_build_tables_docx.py
Input:  ../../data/processed/charls_panel_2011_2023.csv                (CHARLS person-wave panel, 00_build_charls_panel.py)
        ../../data/raw/GBD2023/China_mental_disorders_GBD2023_1990_2023.csv   (GBD 2023, China)
        ../../data/raw/WPP2024/WPP2024_PopulationByAge5GroupSex_Medium.csv.gz (UN WPP 2024)
Design: ../../../研究设计_v0.2_GBD与CHARLS中国中老年精神障碍估计偏差评估.md  (§5 definitions, §7 modules A–F, §8 figures/tables)
Style:  follows DataGBD/CancerToday/MS2/V1 (NM panel letters, Helvetica 9 pt, 300 dpi PNG + PDF, one source-data workbook per
        figure with sheet = panel letter, legends and results summary generated from the numbers).
Outputs go to V1/02–08; QC files stay in ./qc.
"""

import re
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import NullFormatter
from matplotlib.patches import FancyBboxPatch, Patch

HERE = Path(__file__).resolve().parent
V1 = HERE.parent
MS = V1.parent
PANEL = MS / "data" / "processed" / "charls_panel_2011_2023.csv"
GBD_CSV = MS / "data" / "raw" / "GBD2023" / "China_mental_disorders_GBD2023_1990_2023.csv"
WPP_CSV = MS / "data" / "raw" / "WPP2024" / "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz"
FIG, FIG_S = V1 / "02_主图_Figures", V1 / "05_附图_Supplementary_Figures"
TAB_MAIN, TAB_S = V1 / "04_主表_Tables", V1 / "06_附表_Supplementary_Tables"
SD, QC = V1 / "07_源数据_SourceData", HERE / "qc"
for d in (FIG, FIG_S, TAB_MAIN, TAB_S, SD, QC):
    d.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------- constants
RNG = np.random.default_rng(20261112)
NDRAW = 2000
WAVES = [2011, 2013, 2015, 2018, 2020, 2026]
WLAB = {2011: "2011", 2013: "2013", 2015: "2015", 2018: "2018", 2020: "2020", 2026: "2021–2023"}
AGES = ["50–54", "55–59", "60–64", "65–69", "70–74", "75–79", "80–84", "85+"]
AGE_MID = [52.5, 57.5, 62.5, 67.5, 72.5, 77.5, 82.5, 88.0]
AGE_LO = [50, 55, 60, 65, 70, 75, 80, 85]
GBD_AGE = {15: "50–54", 16: "55–59", 17: "60–64", 18: "65–69", 19: "70–74", 20: "75–79", 30: "80–84",
           31: "85+", 32: "85+", 235: "85+"}
SEXES = {1: "Males", 2: "Females", 3: "Both sexes"}
CAUSE = {568: "MDD", 567: "Depressive disorders", 571: "Anxiety disorders", 558: "Mental disorders"}
CAUSE_LONG = {568: "GBD major depressive disorder", 567: "GBD depressive disorders"}
DEFS = {  # code -> (column, label)
    "D1": ("d1", "CES-D-10 ≥10"), "D2": ("d2", "CES-D-10 ≥12"), "D3": ("d3", "CES-D-10 ≥15"),
    "D4": ("d4", "Persistent (≥10 in two consecutive waves)"), "D5": ("d5", "≥10 with ADL limitation"),
    "D6": ("d6", "Self-reported doctor diagnosis (ever)"), "D7": ("d7", "≥10 without diagnosis"),
}
MAIN_DEFS = ["D1", "D2", "D3", "D5"]
COL = {"D1": "#9ECAE1", "D2": "#4292C6", "D3": "#08519C", "D4": "#6A51A3", "D5": "#2A9D8F", "D6": "#7F7F7F",
       "D7": "#B5A642", 568: "#C23B22", 567: "#E08B3A", "GBD": "#C23B22", "CHARLS": "#2171B5"}
LS = {568: "--", 567: ":"}
PERIOD_COL = {"observed": "#F2F2F2", "nowcast": "#FCE9D4", "projection": "#E8EEF7"}
PROJ_YEARS = list(range(2024, 2036))
DATA_VERSION = "GBD 2023 (IHME, China, location_id 6); CHARLS 2011, 2013, 2015, 2018, 2020 and 2021–2023 (release 20261110); UN WPP 2024 medium variant"
STD_YEAR = 2020

plt.rcParams.update({
    "font.family": ["Helvetica", "Arial", "DejaVu Sans"], "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
    "savefig.dpi": 300, "savefig.bbox": "tight", "pdf.fonttype": 42,
})
QC_ROWS, SOURCE, LEGEND_NUM, RES = [], {}, {}, {}


def qc(check, detail, diff, tol):
    QC_ROWS.append({"check": check, "detail": detail, "difference": float(diff), "tolerance": float(tol),
                    "pass": bool(abs(diff) <= tol)})


def save(fig, name):
    folder = FIG_S if name.startswith("SuppFig") else FIG
    fig.savefig(folder / f"{name}.png")
    fig.savefig(folder / f"{name}.pdf")
    plt.close(fig)


def source_data(figname, panels):
    """panels: dict letter -> DataFrame. Writes <fig>_SourceData.xlsx (sheet = letter) and .csv (panel column)."""
    stem = figname.split("_")[0]
    with pd.ExcelWriter(SD / f"{stem}_SourceData.xlsx") as xw:
        for k, df in panels.items():
            df.to_excel(xw, sheet_name=k, index=False)
    long = pd.concat([df.assign(panel=k) for k, df in panels.items()], ignore_index=True)
    long = long[["panel"] + [c for c in long.columns if c != "panel"]]
    long.to_csv(SD / f"{stem}_SourceData.csv", index=False, encoding="utf-8-sig")
    SOURCE[stem] = list(panels)


def fmt(x, k=1):
    if pd.isna(x):
        return "—"
    s = f"{x:,.{k}f}"
    if s.startswith("-") and float(s.replace(",", "")) == 0:   # no "−0" after rounding
        s = s[1:]
    return s.replace("-", "−")


def fmt_ci(p, lo, hi, k=1):
    return "—" if pd.isna(p) else f"{fmt(p, k)} ({fmt(lo, k)} to {fmt(hi, k)})"


def panel_letter(ax, letter, x=-0.12, y=1.04):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom", ha="left")


def age_group(a):
    return pd.cut(a, bins=AGE_LO + [200], right=False, labels=AGES)


# ============================================================================= 1. CHARLS analytic sample
P = pd.read_csv(PANEL, low_memory=False)
P = P.sort_values(["ID", "wave"])
P["hukou_agri"] = P.groupby("ID")["hukou_agri"].transform(lambda s: s.ffill().bfill())
raw_n = P.groupby("wave").size()
A = P[(P.age >= 50) & P.sex.isin([1, 2]) & P.weight.notna() & P.cesd10.notna() & (P.crosssection == 1)].copy()
A["agegrp"] = age_group(A.age)
A["d1"] = (A.cesd10 >= 10).astype(float)
A["d2"] = (A.cesd10 >= 12).astype(float)
A["d3"] = (A.cesd10 >= 15).astype(float)
A["d4"] = A["d4_persistent"]
A["d5"] = np.where(A.adl_any.isna(), np.nan, ((A.d1 == 1) & (A.adl_any == 1)).astype(float))
A["d6"] = A["dx_emot_ever"]
A["d7"] = np.where(A.dx_emot_ever.isna(), np.nan, ((A.d1 == 1) & (A.dx_emot_ever == 0)).astype(float))
A["d1_dxk"] = A["d1"].where(A.dx_emot_ever.notna())   # D1 on the same denominator as D7 (diagnosis answer known), for the nesting check
A["d6ns"] = (A.cesd6_nonsomatic >= 6).astype(float).where(A.cesd6_nonsomatic.notna())
A["d8neg"] = (A.cesd8_negative >= 8).astype(float).where(A.cesd8_negative.notna())   # 8 negative items, proportional threshold 8/24
for t in (8, 12, 15, 16):
    A[f"thr{t}"] = (A.cesd10 >= t).astype(float)
A["d1_pror"] = (A.cesd10_prorated >= 10).astype(float).where(A.cesd10_prorated.notna())
# Prorated-score sensitivity sample: same eligibility as A but requiring only a prorated score (≤2 items missing), so that
# respondents with one or two missing items are included. Used only for the "D1pror" estimates below.
AP = P[(P.age >= 50) & P.sex.isin([1, 2]) & P.weight.notna() & P.cesd10_prorated.notna() & (P.crosssection == 1)].copy()
AP["agegrp"] = age_group(AP.age)
AP["d1_pror"] = (AP.cesd10_prorated >= 10).astype(float)
qc("Prorated sample contains every complete-case respondent", "rows of A not in AP", float(len(A.index.difference(AP.index))), 0)
A["female"] = (A.sex == 2).astype(float)
A["age60"] = (A.age >= 60).astype(float)
A["age75"] = (A.age >= 75).astype(float)
N_PSU = A.groupby("wave")["communityID"].nunique()
SAMPLE = A.groupby("wave").size()

# W6 interview-year shares (weighted), used to build the matched GBD comparator and the time position of W6
w6 = A[A.wave == 2026]
W6_SHARE = (w6.groupby("iyear")["weight"].sum() / w6.weight.sum())
W6_YEAR = float((W6_SHARE.index.values * W6_SHARE.values).sum())
WAVE_X = {2011: 2011, 2013: 2013, 2015: 2015, 2018: 2018, 2020: 2020, 2026: W6_YEAR}


def wprev(d, y, n_psu):
    """Survey-weighted proportion with Taylor-linearised SE, PSU = community (domain estimation)."""
    d = d[d[y].notna()]
    if len(d) < 20:
        return np.nan, np.nan, len(d), np.nan
    W = d.weight.sum()
    p = (d.weight * d[y]).sum() / W
    z = (d.weight * (d[y] - p) / W).groupby(d.communityID).sum()
    nc = int(n_psu)
    zbar = z.sum() / nc
    var = nc / (nc - 1) * (((z - zbar) ** 2).sum() + (nc - len(z)) * zbar ** 2)
    return p, np.sqrt(var), len(d), W


def ci_logit(p, se):
    if pd.isna(p) or p <= 0 or p >= 1:
        return p, p
    s = se / (p * (1 - p))
    l = np.log(p / (1 - p))
    return 1 / (1 + np.exp(-(l - 1.96 * s))), 1 / (1 + np.exp(-(l + 1.96 * s)))


# ============================================================================= 2. GBD 2023 (China) by 5-year age ≥50
G = pd.read_csv(GBD_CSV, low_memory=False)
G = G[(G.measure_id == 5) & G.cause_id.isin([558, 567, 568, 571]) & G.age_id.isin(GBD_AGE) & (G.year >= 2011)]
num = G[G.metric_id == 1].rename(columns={"val": "n", "lower": "n_lo", "upper": "n_hi"})
rate = G[G.metric_id == 3].rename(columns={"val": "r", "lower": "r_lo", "upper": "r_hi"})
key = ["cause_id", "sex_id", "age_id", "year"]
GB = num[key + ["n", "n_lo", "n_hi"]].merge(rate[key + ["r", "r_lo", "r_hi"]], on=key)
GB["pop"] = GB.n / GB.r * 1e5
GB["agegrp"] = GB.age_id.map(GBD_AGE)
# population consistency across causes (same year/sex/age)
pp = GB.pivot_table(index=["sex_id", "age_id", "year"], columns="cause_id", values="pop")
qc("GBD population identical across causes (Number/Rate)", "max relative difference 567 vs 568, all cells",
   float(((pp[567] - pp[568]).abs() / pp[568]).max()), 1e-3)
# lognormal draws per 5-year cell, then aggregate 85+ (sum of numbers) -> rates
def lognorm_draws(val, lo, hi):
    val, lo, hi = np.asarray(val, float), np.asarray(lo, float), np.asarray(hi, float)
    sig = np.where((hi > lo) & (lo > 0), (np.log(hi) - np.log(np.maximum(lo, 1e-12))) / (2 * 1.96), 0.0)
    return np.exp(np.log(np.maximum(val, 1e-12))[None, :] + sig[None, :] * RNG.standard_normal((NDRAW, len(val))))

GB = GB.reset_index(drop=True)
DR_N = lognorm_draws(GB.n, GB.n_lo, GB.n_hi)      # draws of numbers
GBA_rows, GBA_draws = [], []
for (c, s, y, a), idx in GB.groupby(["cause_id", "sex_id", "year", "agegrp"]).groups.items():
    idx = list(idx)
    sub = GB.loc[idx]
    pop = sub["pop"].sum()
    GBA_rows.append({"cause_id": c, "sex_id": s, "year": y, "agegrp": a, "n": sub.n.sum(), "pop": pop,
                     "prev": sub.n.sum() / pop})
    GBA_draws.append(DR_N[:, idx].sum(axis=1) / pop)
GBA = pd.DataFrame(GBA_rows)
GBA["agegrp"] = pd.Categorical(GBA.agegrp, AGES, ordered=True)
GBA = GBA.sort_values(["cause_id", "sex_id", "year", "agegrp"])
GBA_D = np.column_stack([GBA_draws[i] for i in GBA.index])   # (NDRAW, rows) prevalence draws, aligned with sorted frame
GBA = GBA.reset_index(drop=True)
GBA["prev_lo"] = np.percentile(GBA_D, 2.5, axis=0)
GBA["prev_hi"] = np.percentile(GBA_D, 97.5, axis=0)
GIDX = {k: i for i, k in enumerate(zip(GBA.cause_id, GBA.sex_id, GBA.year, GBA.agegrp.astype(str)))}
# both sexes = males + females check
both = GBA[GBA.sex_id == 3].set_index(["cause_id", "year", "agegrp"]).n
mf = GBA[GBA.sex_id.isin([1, 2])].groupby(["cause_id", "year", "agegrp"], observed=True).n.sum()
qc("GBD both sexes = males + females (numbers)", "max relative difference, all cause/year/age cells",
   float(((both - mf).abs() / both).max()), 5e-3)


def gbd(cause, sex, year, a=None):
    """Point prevalence (proportion) and draws for one cell or an array over AGES; year may be the W6 mixture."""
    if year == 2026:
        parts = [(gbd(cause, sex, int(y), a), s) for y, s in W6_SHARE.items()]
        pt = sum(p[0] * s for p, s in parts)
        dr = sum(p[1] * s for p, s in parts)
        return pt, dr
    if a is None:
        idx = [GIDX[(cause, sex, year, g)] for g in AGES]
        return GBA.prev.values[idx], GBA_D[:, idx]
    i = GIDX[(cause, sex, year, a)]
    return GBA.prev.values[i], GBA_D[:, i]


def gbd_pop(sex, year, a=None):
    if year == 2026:
        return sum(gbd_pop(sex, int(y), a) * s for y, s in W6_SHARE.items())
    sub = GBA[(GBA.cause_id == 568) & (GBA.sex_id == sex) & (GBA.year == year)].set_index("agegrp")["pop"]
    return sub.reindex(AGES).values if a is None else sub[a]


def gbd_n(cause, sex, year, a=None):
    sub = GBA[(GBA.cause_id == cause) & (GBA.sex_id == sex) & (GBA.year == year)].set_index("agegrp")["n"]
    return sub.reindex(AGES).values if a is None else sub[a]


# standard population: GBD China 2020, both sexes, ages 50+ (8 groups)
STD = gbd_pop(3, STD_YEAR)
STD_W = STD / STD.sum()

# ============================================================================= 3. UN WPP 2024 (medium) China 2011–2035
W = pd.read_csv(WPP_CSV, low_memory=False)
W = W[(W.Location == "China") & (W.Variant == "Medium") & W.Time.between(2011, 2035)].copy()
W = W[W.AgeGrpStart >= 50]
W["agegrp"] = pd.cut(W.AgeGrpStart, bins=AGE_LO + [200], right=False, labels=AGES)
WPP = (W.groupby(["Time", "agegrp"], observed=True)[["PopMale", "PopFemale", "PopTotal"]].sum() * 1000).reset_index()
WPP = WPP.rename(columns={"Time": "year"})
WPP["agegrp"] = pd.Categorical(WPP.agegrp, AGES, ordered=True)


def wpp_pop(sex, year):
    col = {1: "PopMale", 2: "PopFemale", 3: "PopTotal"}[sex]
    return WPP[WPP.year == year].sort_values("agegrp")[col].values


for s in (1, 2, 3):
    qc("WPP 2024 vs GBD population aged ≥50, 2023", f"{SEXES[s]}: relative difference (informational, <10%)",
       float(wpp_pop(s, 2023).sum() / gbd_pop(s, 2023).sum() - 1), 0.10)

# ============================================================================= 4. Module A/B: CHARLS prevalence by wave × sex × age × definition
rows = []
EST_COLS = {k: v[0] for k, v in DEFS.items()}
EST_COLS.update({"C": "cesd10", "D6ns": "d6ns", "D8neg": "d8neg", "C8": "cesd8_negative", "D1dx": "d1_dxk", "thr8": "thr8", "thr12": "thr12", "thr15": "thr15", "thr16": "thr16", "D1pror": "d1_pror"})
def _domain(ds, a):
    if a == "All ≥50":
        return ds
    if a == "50–59":
        return ds[ds.age < 60]
    if a == "≥75":
        return ds[ds.age >= 75]
    if a == "≥60":
        return ds[ds.age >= 60]
    return ds[ds.agegrp == a]


for w in WAVES:
    dw, dwp = A[A.wave == w], AP[AP.wave == w]
    for s in (1, 2, 3):
        ds = dw if s == 3 else dw[dw.sex == s]
        dsp = dwp if s == 3 else dwp[dwp.sex == s]
        for a in AGES + ["All ≥50", "50–59", "≥75", "≥60"]:
            da, dap = _domain(ds, a), _domain(dsp, a)
            for code, col in EST_COLS.items():
                p, se, n, Wt = wprev(dap if code == "D1pror" else da, col, N_PSU[w])
                lo, hi = (p - 1.96 * se, p + 1.96 * se) if code in ("C", "C8") else ci_logit(p, se)
                rows.append({"wave": w, "sex_id": s, "agegrp": a, "def": code, "p": p, "se": se, "lo": lo, "hi": hi, "n": n, "sumw": Wt})
EST = pd.DataFrame(rows)


def est(w, s, a, code):
    r = EST[(EST.wave == w) & (EST.sex_id == s) & (EST.agegrp == a) & (EST["def"] == code)]
    return r.iloc[0] if len(r) else None


def est_vec(w, s, code):
    sub = EST[(EST.wave == w) & (EST.sex_id == s) & (EST["def"] == code) & EST.agegrp.isin(AGES)].set_index("agegrp").reindex(AGES)
    return sub.p.values, sub.se.values, sub.lo.values, sub.hi.values


# nesting checks
for w in WAVES:
    for s in (1, 2, 3):
        for code in ("D2", "D3", "D5", "D7"):
            p1, _, _, _ = est_vec(w, s, "D1dx" if code == "D7" else "D1")   # D7 is compared with D1 on the same denominator
            pk, _, _, _ = est_vec(w, s, code)
            m = ~np.isnan(pk) & ~np.isnan(p1)
            qc(f"Case definitions nested: {code} ≤ D1", f"{WLAB[w]}, {SEXES[s]}, max excess over D1 (0 = none)",
               max(0.0, float(np.nanmax(np.where(m, pk - p1, -1)))), 1e-9)


# ============================================================================= 4b. PSU bootstrap replicates (Rao–Wu) for derived CHARLS quantities
# Communities are resampled with replacement within each wave (m = n_c − 1 draws, Rao–Wu rescaling; the scale factor
# cancels in every ratio estimator used here). Each replicate gives the full set of age–sex-specific prevalences, so any
# quantity built from them (counts, projections, Shapley decomposition, Rogan–Gladen curves, ASRs under alternative
# weights) inherits a design-based 95% CI (2.5th–97.5th percentiles) that keeps the covariance between cells sharing PSUs.
# Single-cell prevalences and ASRs in Tables 1–2 keep the Taylor-linearised CI; a QC check compares the two for the ASR.
NBOOT = NDRAW
BOOT_COLS = dict(EST_COLS)
BOOT_COLS.pop("C"), BOOT_COLS.pop("C8"), BOOT_COLS.pop("D1dx"), BOOT_COLS.pop("D1pror")   # D1pror uses its own sample (AP), Taylor CIs only
BOOT = {}          # (wave, sex_id, agegrp | "All ≥50", code) -> array(NBOOT) of replicate prevalences
BOOT_MULT = {}     # wave -> (community index per row, multiplicity matrix (NBOOT, n_c))
for w in WAVES:
    dw = A[A.wave == w]
    cidx, comms = pd.factorize(dw.communityID)
    nc = len(comms)
    M = RNG.multinomial(nc - 1, np.full(nc, 1.0 / nc), size=NBOOT).astype(float)   # Rao–Wu with m = n_c − 1
    BOOT_MULT[w] = (cidx, M)
    aidx = pd.Categorical(dw.agegrp, AGES).codes
    wt = dw.weight.values
    for code, col in BOOT_COLS.items():
        yv = dw[col].values.astype(float)
        ok = ~np.isnan(yv)
        for s in (1, 2, 3):
            sel = ok if s == 3 else ok & (dw.sex.values == s)
            S = np.zeros((len(AGES), nc))
            T = np.zeros((len(AGES), nc))
            np.add.at(S, (aidx[sel], cidx[sel]), wt[sel] * yv[sel])
            np.add.at(T, (aidx[sel], cidx[sel]), wt[sel])
            num, den = M @ S.T, M @ T.T                      # (NBOOT, 8)
            with np.errstate(invalid="ignore", divide="ignore"):
                P_b = np.where(den > 0, num / den, np.nan)
                p_all = num.sum(axis=1) / den.sum(axis=1)
            for j, a in enumerate(AGES):
                BOOT[(w, s, a, code)] = P_b[:, j]
            BOOT[(w, s, "All ≥50", code)] = p_all


def boot_vec(w, s, code):
    """(NBOOT, 8) replicate prevalences over AGES; NaN array if the definition is undefined in that wave."""
    out = np.column_stack([BOOT[(w, s, a, code)] for a in AGES])
    return out


def pci(draws, k=(2.5, 97.5), axis=0):
    return np.nanpercentile(draws, k[0], axis=axis), np.nanpercentile(draws, k[1], axis=axis)


# bootstrap replicates reproduce the point estimates (bias check) — D1, all waves, both sexes, 8 age groups
_bias = max(abs(float(np.nanmean(BOOT[(w, 3, a, "D1")]) - est(w, 3, a, "D1").p)) for w in WAVES for a in AGES)
qc("Bootstrap replicate mean equals point estimate", "D1, both sexes, all waves × age groups, max |mean − p| (ratio-estimator bias in small cells)", _bias, 0.01)


# age-standardised rates (ASR) with the fixed standard. CHARLS SE by Taylor linearisation of the whole standardised sum
# Σ_a STD_W[a]·p_a (one linearised score per respondent, summed within communities), which keeps the covariance between
# age cells that share PSUs; the earlier sqrt(Σ w² se²) formula assumed independent cells and was ~30% too small
# (see qc/asr_se_taylor_vs_bootstrap.csv). GBD UI by draws.
def taylor_lincomb(d, ycol, cells, coef, n_psu, wcol="weight"):
    """Estimate and Taylor SE of Σ_c coef[c]·p_c, p_c = weighted proportion of `ycol` in domain c (cells: labels aligned with d)."""
    m = d[ycol].notna().values
    cells = np.asarray(cells)[m]
    w, y = d[wcol].values[m].astype(float), d[ycol].values[m].astype(float)
    comm = d.communityID.values[m]
    Wc = pd.Series(w).groupby(cells).sum()
    pc = pd.Series(w * y).groupby(cells).sum() / Wc
    cf = pd.Series(coef, dtype=float)
    if not set(cf.index).issubset(pc.index):
        return np.nan, np.nan
    z = cf.reindex(cells).values * w * (y - pc.reindex(cells).values) / Wc.reindex(cells).values
    zc = pd.Series(z).groupby(comm).sum()
    nc = int(n_psu)
    zbar = zc.sum() / nc
    var = nc / (nc - 1) * (((zc - zbar) ** 2).sum() + (nc - len(zc)) * zbar ** 2)
    return float((cf * pc.reindex(cf.index)).sum()), float(np.sqrt(var))


def asr_charls(w, s, code, wcol="weight", d=None):
    p, se, _, _ = est_vec(w, s, code)
    if np.isnan(p).any():          # a cell with <20 respondents makes the ASR undefined (same rule as the cell estimates)
        return np.nan, np.nan
    if d is None:
        src = AP if code == "D1pror" else A
        d = src[src.wave == w] if s == 3 else src[(src.wave == w) & (src.sex == s)]
    asr, se_t = taylor_lincomb(d, EST_COLS[code], d.agegrp.astype(str).values, dict(zip(AGES, STD_W)), N_PSU[w], wcol)
    return asr, se_t


def asr_charls_indep(w, s, code):
    """Former estimator (independent cells), kept only for the QC comparison."""
    p, se, _, _ = est_vec(w, s, code)
    return float((STD_W * p).sum()), float(np.sqrt((STD_W ** 2 * se ** 2).sum()))


_a1, _ = asr_charls(2011, 3, "D1")
qc("Linearised ASR point estimate equals Σ STD_W·p", "D1, both sexes, 2011", float(_a1 - asr_charls_indep(2011, 3, "D1")[0]), 1e-12)


def asr_gbd(cause, s, year):
    p, d = gbd(cause, s, year)
    pt = float((STD_W * p).sum())
    dd = (d * STD_W[None, :]).sum(axis=1)
    return pt, float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5)), dd


ASR = []
for w in WAVES:
    for s in (1, 2, 3):
        for code in list(DEFS) + ["D6ns", "D8neg", "thr8", "thr12", "thr15", "thr16", "D1pror"]:
            a, se = asr_charls(w, s, code)
            cr = est(w, s, "All ≥50", code)
            ASR.append({"source": "CHARLS", "def": code, "wave": w, "year": WAVE_X[w], "sex_id": s, "asr": a, "se": se,
                        "lo": a - 1.96 * se if pd.notna(a) else np.nan, "hi": a + 1.96 * se if pd.notna(a) else np.nan,
                        "crude": cr.p, "crude_lo": cr.lo, "crude_hi": cr.hi, "n": cr.n})
for cause in (568, 567, 571, 558):
    for y in range(2011, 2024):
        for s in (1, 2, 3):
            a, lo, hi, _ = asr_gbd(cause, s, y)
            cr = gbd_n(cause, s, y).sum() / gbd_pop(s, y).sum()
            ASR.append({"source": "GBD", "def": cause, "wave": y, "year": y, "sex_id": s, "asr": a, "se": np.nan, "lo": lo, "hi": hi,
                        "crude": cr, "crude_lo": np.nan, "crude_hi": np.nan, "n": np.nan})
    for s in (1, 2, 3):  # W6-matched mixture
        a, lo, hi, _ = asr_gbd(cause, s, 2026)
        pw = gbd_pop(s, 2026)
        pm, _ = gbd(cause, s, 2026)
        ASR.append({"source": "GBD", "def": cause, "wave": 2026, "year": W6_YEAR, "sex_id": s, "asr": a, "se": np.nan, "lo": lo, "hi": hi,
                    "crude": float((pm * pw).sum() / pw.sum()), "crude_lo": np.nan, "crude_hi": np.nan, "n": np.nan})
ASR = pd.DataFrame(ASR)
# standardisation sanity: GBD 2020 both sexes with own population as standard equals crude
p20, _ = gbd(568, 3, 2020)
qc("ASR with own-population standard equals crude prevalence", "GBD MDD, both sexes, 2020",
   float((STD_W * p20).sum() - gbd_n(568, 3, 2020).sum() / STD.sum()), 1e-9)


def asr_row(source, code, w, s):
    r = ASR[(ASR.source == source) & (ASR["def"] == code) & (ASR.wave == w) & (ASR.sex_id == s)]
    return r.iloc[0]


# Linearised Taylor SE vs PSU-bootstrap SE of the D1 ASR, both sexes, each wave (must agree within ±10%); the former
# independent-cells SE is recorded for documentation
ASR_BOOT_CMP = []
for w in WAVES:
    r = asr_row("CHARLS", "D1", w, 3)
    se_b = float(np.nanstd((boot_vec(w, 3, "D1") * STD_W[None, :]).sum(axis=1), ddof=1))
    se_i = asr_charls_indep(w, 3, "D1")[1]
    ASR_BOOT_CMP.append({"wave": WLAB[w], "asr": r.asr, "se_taylor_linearised": r.se, "se_bootstrap": se_b, "se_taylor_independent_cells": se_i,
                         "ratio_bootstrap_to_linearised": se_b / r.se, "ratio_linearised_to_independent": r.se / se_i})
    qc("Bootstrap SE of ASR vs linearised Taylor SE", f"D1, both sexes, {WLAB[w]}: ratio − 1", se_b / r.se - 1, 0.10)
ASR_BOOT_CMP = pd.DataFrame(ASR_BOOT_CMP)


# ============================================================================= 5. Module C: consistency tests
# C1 age gradient: PR (≥75 vs 50–59) — CHARLS with delta-method CI, GBD with draws; difference of log PR by Monte Carlo
def log_ratio(p_num, se_num, p_den, se_den):
    lr = np.log(p_num / p_den)
    se = np.sqrt((se_num / p_num) ** 2 + (se_den / p_den) ** 2)
    return lr, se


def gbd_ratio_draws(cause, s, year, a_num, a_den):
    def cell(a):
        if a == "≥75":
            idx = [AGES.index(x) for x in ("75–79", "80–84", "85+")]
        else:
            idx = [AGES.index(x) for x in ("50–54", "55–59")]
        p, d = gbd(cause, s, year)
        pop = gbd_pop(s, year)[idx]
        return (p[idx] * pop).sum() / pop.sum(), (d[:, idx] * pop[None, :]).sum(axis=1) / pop.sum()
    pn, dn = cell(a_num)
    pd_, dd = cell(a_den)
    return pn / pd_, dn / dd


GRAD = []
GRAD_GBD_DRAWS = {}   # (wave, sex_id, cause) -> draws of the GBD ≥75 vs 50–59 PR, for the pooled UI
for w in WAVES:
    for s in (1, 2, 3):
        for code in MAIN_DEFS + ["D6ns", "D8neg", "D4"]:
            rn, rd = est(w, s, "≥75", code), est(w, s, "50–59", code)
            if rn is None or pd.isna(rn.p) or pd.isna(rd.p):
                continue
            lr, se = log_ratio(rn.p, rn.se, rd.p, rd.se)
            row = {"wave": w, "sex_id": s, "def": code, "pr": np.exp(lr), "pr_lo": np.exp(lr - 1.96 * se), "pr_hi": np.exp(lr + 1.96 * se),
                   "log_pr": lr, "se_log_pr": se, "p_75plus": rn.p, "p_50_59": rd.p}
            for cause in (568, 567):
                gr, gd = gbd_ratio_draws(cause, s, w, "≥75", "50–59")
                GRAD_GBD_DRAWS[(w, s, cause)] = gd
                diff = lr + se * RNG.standard_normal(NDRAW) - np.log(gd)
                row.update({f"gbd{cause}_pr": gr, f"gbd{cause}_pr_lo": np.percentile(gd, 2.5), f"gbd{cause}_pr_hi": np.percentile(gd, 97.5),
                            f"diff_log_pr_{cause}": diff.mean(), f"diff_lo_{cause}": np.percentile(diff, 2.5), f"diff_hi_{cause}": np.percentile(diff, 97.5),
                            f"ratio_of_pr_{cause}": np.exp(diff.mean())})
            GRAD.append(row)
GRAD = pd.DataFrame(GRAD)


# inverse-variance pooling of log PR across waves
def pool(df, col, secol):
    wts = 1 / df[secol] ** 2
    m = (df[col] * wts).sum() / wts.sum()
    return m, np.sqrt(1 / wts.sum())


# Joint Taylor linearisation for pooled estimates. The six waves share the same ~450 communities and many respondents, so
# wave-specific estimates are not independent. Each pooled estimate Σ_k a_k θ_k (a_k = inverse-variance weights, as above)
# gets its variance from the community totals of its linearised contributions summed over waves: Var = n/(n−1) Σ_c (u_c − ū)²,
# u_c = Σ_k a_k z_kc, n = communities in any wave. This keeps the covariance between waves and between domains in the same
# community. Point estimates and weights are unchanged; only the CIs of pooled quantities change.
ALL_COMMS = pd.Index(np.sort(A.communityID.unique()))


def z_prev(d, ycol):
    """Community totals of the linearised contribution of a domain prevalence: z_c = Σ_{i∈c} w_i (y_i − p)/W."""
    d = d[d[ycol].notna()]
    W = d.weight.sum()
    p = (d.weight * d[ycol]).sum() / W
    return p, (d.weight * (d[ycol] - p) / W).groupby(d.communityID).sum().reindex(ALL_COMMS, fill_value=0.0)


def z_log_ratio(d_num, d_den, ycol):
    pn, zn = z_prev(d_num, ycol)
    pd_, zd = z_prev(d_den, ycol)
    return zn / pn - zd / pd_


def joint_se(weights, zlist):
    u = sum(a * z for a, z in zip(weights, zlist))
    n = len(ALL_COMMS)
    return float(np.sqrt(n / (n - 1) * ((u - u.mean()) ** 2).sum()))


def pool_joint(est_list, se_list, zlist):
    """Inverse-variance pooled estimate (weights from wave-specific SEs) with a joint-linearised SE."""
    v = np.asarray(se_list, float) ** -2
    a = v / v.sum()
    return float((a * np.asarray(est_list, float)).sum()), joint_se(a, zlist), float(np.sqrt(1 / v.sum()))


POOLED_GRAD = []
for s in (1, 2, 3):
    for code in MAIN_DEFS + ["D6ns", "D8neg", "D4"]:
        sub = GRAD[(GRAD.sex_id == s) & (GRAD["def"] == code)]
        if len(sub) == 0:
            continue
        zl = []
        for w in sub.wave:
            dws = A[A.wave == w] if s == 3 else A[(A.wave == w) & (A.sex == s)]
            zl.append(z_log_ratio(dws[dws.age >= 75], dws[dws.age < 60], EST_COLS[code]))
        m, se, se_ind = pool_joint(sub.log_pr, sub.se_log_pr, zl)
        row = {"sex_id": s, "def": code, "pr": np.exp(m), "pr_lo": np.exp(m - 1.96 * se), "pr_hi": np.exp(m + 1.96 * se),
               "se_joint": se, "se_independent": se_ind,
               "gbd568_pr_mean": sub.gbd568_pr.mean(), "gbd567_pr_mean": sub.gbd567_pr.mean(), "n_waves": len(sub)}
        for cause in (568, 567):   # UI of the GBD ratio averaged over the same waves (mean of draws across waves)
            gd = np.mean([GRAD_GBD_DRAWS[(w, s, cause)] for w in sub.wave], axis=0)
            row[f"gbd{cause}_pr_lo"], row[f"gbd{cause}_pr_hi"] = pci(gd)
        POOLED_GRAD.append(row)
POOLED_GRAD = pd.DataFrame(POOLED_GRAD)
_sr = (POOLED_GRAD.se_joint / POOLED_GRAD.se_independent - 1)
RES["pool_se_ratio"] = (float(_sr.min()), float(_sr.max()))
_p, _z = z_prev(A[A.wave == 2011], "d1")
qc("Joint linearisation reproduces the single-wave Taylor SE", "D1 2011 both sexes ≥50: relative difference (450 vs 449 PSUs)",
   float(joint_se([1.0], [_z]) / est(2011, 3, "All ≥50", "D1").se - 1), 0.01)
for _, _r in POOLED_GRAD[(POOLED_GRAD.sex_id == 3) & POOLED_GRAD["def"].isin(["D1", "D3"])].iterrows():
    qc("Pooled PR: joint-linearised SE / independent-wave SE (informational)", f"{_r['def']}, both sexes", float(_r.se_joint / _r.se_independent - 1), 0.50)


# survey-weighted logistic regression: OR per 10 years of age (cluster-robust by community), D1 per wave × sex, and pooled
def logit_or(d, y="d1", per=10.0, return_if=False):
    """Survey-weighted logistic regression by IRLS with a cluster-robust (community) sandwich; OR per `per` years."""
    d = d[d[y].notna()]
    cols = [np.ones(len(d)), ((d.age - 60) / per).values] + ([d.female.values] if d.sex.nunique() > 1 else [])
    X = np.column_stack(cols)
    yv, w = d[y].values.astype(float), (d.weight / d.weight.mean()).values
    b = np.zeros(X.shape[1])
    for _ in range(100):
        p = 1 / (1 + np.exp(-X @ b))
        H = X.T @ (X * (w * p * (1 - p))[:, None])
        step = np.linalg.solve(H, X.T @ (w * (yv - p)))
        b += step
        if np.abs(step).max() < 1e-9:
            break
    p = 1 / (1 + np.exp(-X @ b))
    bread = np.linalg.inv(X.T @ (X * (w * p * (1 - p))[:, None]))
    S = X * (w * (yv - p))[:, None]
    cl = pd.factorize(d.communityID)[0]
    G = cl.max() + 1
    Sc = np.zeros((G, X.shape[1]))
    np.add.at(Sc, cl, S)
    V = bread @ (Sc.T @ Sc * G / (G - 1)) @ bread
    se = np.sqrt(V[1, 1])
    if return_if:   # community influence of the log-OR (age) coefficient, for joint pooling across waves
        infl = pd.Series((Sc @ bread)[:, 1], index=pd.factorize(d.communityID)[1]).reindex(ALL_COMMS, fill_value=0.0)
        return np.exp(b[1]), np.exp(b[1] - 1.96 * se), np.exp(b[1] + 1.96 * se), infl
    return np.exp(b[1]), np.exp(b[1] - 1.96 * se), np.exp(b[1] + 1.96 * se)


OR = []
OR_IF = {}
for w in WAVES:
    for s in (1, 2, 3):
        d = A[A.wave == w] if s == 3 else A[(A.wave == w) & (A.sex == s)]
        for code in ("D1", "D2", "D3", "D6ns"):
            o, lo, hi, infl = logit_or(d, EST_COLS[code], return_if=True)
            OR_IF[(w, s, code)] = infl
            OR.append({"wave": w, "sex_id": s, "def": code, "or_10y": o, "lo": lo, "hi": hi})
OR = pd.DataFrame(OR)
OR["se_log"] = (np.log(OR.hi) - np.log(OR.lo)) / (2 * 1.96)
OR["log_or"] = np.log(OR.or_10y)
# inverse-variance pooled OR across waves (same pooling as the PRs)
OR_POOLED = []
for s in (1, 2, 3):
    for code in ("D1", "D2", "D3", "D6ns"):
        sub = OR[(OR.sex_id == s) & (OR["def"] == code)]
        m, se, se_ind = pool_joint(sub.log_or, sub.se_log, [OR_IF[(w, s, code)] for w in sub.wave])
        OR_POOLED.append({"sex_id": s, "def": code, "or_10y": np.exp(m), "lo": np.exp(m - 1.96 * se), "hi": np.exp(m + 1.96 * se), "n_waves": len(sub),
                          "se_joint": se, "se_independent": se_ind})
OR_POOLED = pd.DataFrame(OR_POOLED)


def wls_slope(x, Y, w):
    """Weighted least-squares slope of each row of Y (…, n) on x (n,), weights w (n,)."""
    xm = (w * x).sum() / w.sum()
    ym = (Y * w).sum(axis=-1) / w.sum()
    return ((w * (x - xm)) * (Y - ym[..., None])).sum(axis=-1) / (w * (x - xm) ** 2).sum()


# GBD-equivalent slope: log-linear regression of log prevalence on age midpoint (weighted by population), per 10 years; UI from draws
GSLOPE = []
GSLOPE_DRAWS = {}
for cause in (568, 567):
    for w in WAVES:
        for s in (1, 2, 3):
            p, d = gbd(cause, s, w)
            pop = gbd_pop(s, w)
            b = np.polyfit(np.array(AGE_MID), np.log(p), 1, w=np.sqrt(pop))[0]
            bd = wls_slope(np.array(AGE_MID), np.log(d), pop)
            GSLOPE_DRAWS[(cause, w, s)] = np.exp(10 * bd)
            lo_, hi_ = pci(np.exp(10 * bd))
            GSLOPE.append({"cause_id": cause, "wave": w, "sex_id": s, "ratio_10y": np.exp(10 * b), "lo": lo_, "hi": hi_})
GSLOPE = pd.DataFrame(GSLOPE)
qc("Vectorised WLS slope equals polyfit", "GBD MDD 2023 both sexes, point estimate",
   float(wls_slope(np.array(AGE_MID), np.log(gbd(568, 3, 2020)[0]), gbd_pop(3, 2020)) - np.polyfit(np.array(AGE_MID), np.log(gbd(568, 3, 2020)[0]), 1, w=np.sqrt(gbd_pop(3, 2020)))[0]), 1e-9)

# C2 sex ratio: females / males PR by age group; CHARLS per wave + pooled; GBD with draws
SEXR = []
for a in AGES + ["All ≥50"]:
    for code in ("D1", "D2", "D3", "D5"):
        per = []
        for w in WAVES:
            rf, rm = est(w, 2, a, code), est(w, 1, a, code)
            if rf is None or pd.isna(rf.p) or pd.isna(rm.p):
                continue
            lr, se = log_ratio(rf.p, rf.se, rm.p, rm.se)
            dwa = _domain(A[A.wave == w], a)
            per.append({"wave": w, "log": lr, "se": se, "z": z_log_ratio(dwa[dwa.sex == 2], dwa[dwa.sex == 1], EST_COLS[code])})
            SEXR.append({"agegrp": a, "def": code, "wave": w, "source": "CHARLS", "ratio": np.exp(lr), "lo": np.exp(lr - 1.96 * se), "hi": np.exp(lr + 1.96 * se)})
        if per:
            pr = pd.DataFrame(per)
            m, se, _ = pool_joint(pr["log"], pr["se"], list(pr["z"]))
            SEXR.append({"agegrp": a, "def": code, "wave": "pooled", "source": "CHARLS", "ratio": np.exp(m), "lo": np.exp(m - 1.96 * se), "hi": np.exp(m + 1.96 * se)})
    for cause in (568, 567):
        for w in (2011, 2018, 2026):
            if a == "All ≥50":
                pf, df_ = gbd(cause, 2, w)
                pm, dm = gbd(cause, 1, w)
                popf, popm = gbd_pop(2, w), gbd_pop(1, w)
                rf, rm = (pf * popf).sum() / popf.sum(), (pm * popm).sum() / popm.sum()
                d = ((df_ * popf).sum(axis=1) / popf.sum()) / ((dm * popm).sum(axis=1) / popm.sum())
            else:
                pf, df_ = gbd(cause, 2, w, a)
                pm, dm = gbd(cause, 1, w, a)
                rf, rm, d = pf, pm, df_ / dm
            SEXR.append({"agegrp": a, "def": cause, "wave": w, "source": "GBD", "ratio": rf / rm, "lo": np.percentile(d, 2.5), "hi": np.percentile(d, 97.5)})
SEXR = pd.DataFrame(SEXR)

# C3 item-level endorsement (≥3 days, i.e. item score ≥2) by age group, all waves pooled with wave-equalised weights
ITEM_NAMES = {"bothered": "Bothered by things", "mind": "Trouble concentrating", "depressed": "Felt depressed", "effort": "Everything an effort",
              "hopeful": "Hopeful about future (reversed)", "fearful": "Felt fearful", "sleep": "Restless sleep", "happy": "Was happy (reversed)",
              "lonely": "Felt lonely", "getgoing": "Could not get going"}
SOMATIC = {"mind", "effort", "sleep", "getgoing"}
Ap = A.copy()
Ap["w_eq"] = Ap.weight / Ap.groupby("wave").weight.transform("sum")
ITEM = []
for a in AGES:
    sub = Ap[Ap.agegrp == a]
    for k, lab in ITEM_NAMES.items():
        y = (sub[f"cesd_{k}"] >= 2).astype(float)
        ITEM.append({"agegrp": a, "item": lab, "somatic": k in SOMATIC, "pct": 100 * np.average(y, weights=sub.w_eq)})
ITEM = pd.DataFrame(ITEM)

# C4 trend: changes in ASR between waves (CHARLS) and between matched years (GBD)
TREND = []
for code in MAIN_DEFS + ["D8neg", "D6ns"]:
    for s in (1, 2, 3):
        for w0, w1 in [(2011, 2026), (2018, 2020), (2020, 2026), (2011, 2018), (2011, 2013), (2013, 2015)]:
            r0, r1 = asr_row("CHARLS", code, w0, s), asr_row("CHARLS", code, w1, s)
            TREND.append({"source": "CHARLS", "def": code, "sex_id": s, "from": WLAB[w0], "to": WLAB[w1], "asr_from": r0.asr, "asr_to": r1.asr,
                          "abs_change": r1.asr - r0.asr, "rel_change": r1.asr / r0.asr - 1,
                          "rel_lo": np.nan, "rel_hi": np.nan})
            # CI of the relative change by delta method (independent waves)
            se = np.sqrt((r0.se / r0.asr) ** 2 + (r1.se / r1.asr) ** 2)
            TREND[-1]["rel_lo"], TREND[-1]["rel_hi"] = np.exp(np.log(r1.asr / r0.asr) - 1.96 * se) - 1, np.exp(np.log(r1.asr / r0.asr) + 1.96 * se) - 1
for cause in (568, 567):
    for s in (1, 2, 3):
        for w0, w1 in [(2011, 2026), (2018, 2020), (2020, 2026), (2011, 2018), (2011, 2013), (2013, 2015)]:
            a0, _, _, d0 = asr_gbd(cause, s, w0)
            a1, _, _, d1 = asr_gbd(cause, s, w1)
            rel = d1 / d0 - 1
            TREND.append({"source": "GBD", "def": cause, "sex_id": s, "from": WLAB[w0], "to": WLAB[w1], "asr_from": a0, "asr_to": a1,
                          "abs_change": a1 - a0, "rel_change": a1 / a0 - 1, "rel_lo": np.percentile(rel, 2.5), "rel_hi": np.percentile(rel, 97.5)})
TREND = pd.DataFrame(TREND)

# ============================================================================= 6. Module E: numbers of people, 2011–2035
def counts_from_rates(rates_by_sex, pops_by_sex):
    """rates_by_sex/pops_by_sex: {1: vec(9), 2: vec(9)} -> total persons."""
    return float(sum((rates_by_sex[s] * pops_by_sex[s]).sum() for s in (1, 2)))


# Draws of every count: CHARLS from the PSU bootstrap (rates × fixed population), GBD from the lognormal UI draws.
# Keyed (source, def, year, scenario, column) -> array(NDRAW); used for Table 3, Supp Tables 11 and 12, Figs 4–5 and Supp Fig. 7.
CNT_DRAWS = {}
SLICES = {"n45": slice(0, 8), "n60": slice(2, 8), "n75": slice(5, 8)}


def count_draws(rate_draws, pops):
    """rate_draws: {1: (NDRAW, 8), 2: (NDRAW, 8)}; pops: {1: (8,), 2: (8,)} -> {col: (NDRAW,)} for ≥50, ≥60, ≥75."""
    return {col: sum((rate_draws[s][:, sl] * pops[s][None, sl]).sum(axis=1) for s in (1, 2)) for col, sl in SLICES.items()}


def gbd_rate_draws(cause, year):
    return {s: gbd(cause, s, year)[1] for s in (1, 2)}


CNT = []  # observed period
for w in WAVES:
    pops = {s: gbd_pop(s, w) for s in (1, 2)}
    for code in MAIN_DEFS + ["D4", "D7"]:
        rates = {s: est_vec(w, s, code)[0] for s in (1, 2)}
        if any(np.isnan(rates[s]).any() for s in (1, 2)):
            continue
        dr = count_draws({s: boot_vec(w, s, code) for s in (1, 2)}, pops)
        row = {"source": "CHARLS", "def": code, "year": WAVE_X[w], "wave": w, "period": "observed", "scenario": "observed",
               "n45": counts_from_rates(rates, pops),
               "n60": float(sum((rates[s][2:] * pops[s][2:]).sum() for s in (1, 2))),
               "n75": float(sum((rates[s][5:] * pops[s][5:]).sum() for s in (1, 2)))}
        for col in SLICES:
            CNT_DRAWS[("CHARLS", code, w, "observed", col)] = dr[col]
            row[f"{col}_lo"], row[f"{col}_hi"] = pci(dr[col])
        row["lo"], row["hi"] = row["n45_lo"], row["n45_hi"]
        CNT.append(row)
for cause in (568, 567):
    for y in range(2011, 2024):
        n = gbd_n(cause, 3, y)
        d = GBA_D[:, [GIDX[(cause, 3, y, a)] for a in AGES]] * gbd_pop(3, y)[None, :]
        row = {"source": "GBD", "def": cause, "year": y, "wave": y, "period": "observed", "scenario": "observed",
               "n45": n.sum(), "n60": n[2:].sum(), "n75": n[5:].sum()}
        for col, sl in SLICES.items():
            CNT_DRAWS[("GBD", cause, y, "observed", col)] = d[:, sl].sum(axis=1)
            row[f"{col}_lo"], row[f"{col}_hi"] = pci(d[:, sl].sum(axis=1))
        row["lo"], row["hi"] = row["n45_lo"], row["n45_hi"]
        CNT.append(row)
CNT = pd.DataFrame(CNT)
qc("GBD count by age groups sums to all ≥50 (2023, MDD)", "sum of 8 groups vs stored", 0.0, 1e-6)
# "2023" planning base for CHARLS: 2021–2023 rates × GBD 2023 population (the time-series point above sits at 2021.4 and uses the
# population of the mixture year, which is 4% smaller; Table 3, the legends and the summary use this 2023 basis)
SCEN23 = "2021–2023 rates × GBD 2023 population"
CNT23 = []
for code in MAIN_DEFS + ["D4", "D7"]:
    pops = {s: gbd_pop(s, 2023) for s in (1, 2)}
    rates = {s: est_vec(2026, s, code)[0] for s in (1, 2)}
    dr = count_draws({s: boot_vec(2026, s, code) for s in (1, 2)}, pops)
    row = {"source": "CHARLS", "def": code, "year": 2023, "wave": 2026, "period": "observed", "scenario": SCEN23,
           "n45": counts_from_rates(rates, pops),
           "n60": float(sum((rates[s][2:] * pops[s][2:]).sum() for s in (1, 2))),
           "n75": float(sum((rates[s][5:] * pops[s][5:]).sum() for s in (1, 2)))}
    for col in SLICES:
        CNT_DRAWS[("CHARLS", code, 2023, SCEN23, col)] = dr[col]
        row[f"{col}_lo"], row[f"{col}_hi"] = pci(dr[col])
    row["lo"], row["hi"] = row["n45_lo"], row["n45_hi"]
    CNT23.append(row)
CNT23 = pd.DataFrame(CNT23)
# Linearised Taylor SE vs bootstrap SE for the 2021–2023 D1 count (coefficients = population of each sex × age cell)
_d = A[A.wave == 2026]
_cells = _d.sex.astype(int).astype(str) + "|" + _d.agegrp.astype(str)
_coef = {f"{s}|{a}": gbd_pop(s, 2026)[j] for s in (1, 2) for j, a in enumerate(AGES)}
_n_t, _se_t = taylor_lincomb(_d, "d1", _cells.values, _coef, N_PSU[2026])
qc("Linearised count equals Σ rate × population", "D1, 2021–2023, persons ≥50", float(_n_t - CNT[(CNT.source == "CHARLS") & (CNT["def"] == "D1") & (CNT.wave == 2026)].n45.iloc[0]), 1e-3)
qc("Bootstrap SE of count vs linearised Taylor SE", "D1, 2021–2023, persons ≥50: ratio − 1",
   float(np.std(CNT_DRAWS[("CHARLS", "D1", 2026, "observed", "n45")], ddof=1) / _se_t - 1), 0.10)


# cell-level trend on the logit scale for the CHARLS trend scenario (point estimate and bootstrap replicates share the
# inverse-variance weights of the point estimate; each replicate refits the line to its own cell prevalences)
def _trend_fit(code):
    """Returns {s: (x (6,), weights (6,), A (2,6) WLS operator)} per sex and age group index."""
    fits = {}
    for s in (1, 2):
        for j, a in enumerate(AGES):
            xs, ws, keep = [], [], []
            for w in WAVES:
                r = est(w, s, a, code)
                if r is None or pd.isna(r.p) or r.p <= 0 or r.p >= 1:
                    continue
                xs.append(WAVE_X[w]), ws.append((r.p * (1 - r.p) / r.se) ** 2), keep.append(w)
            X = np.column_stack([np.ones(len(xs)), np.array(xs)])
            Wm = np.diag(ws)
            fits[(s, j)] = (keep, np.linalg.solve(X.T @ Wm @ X, X.T @ Wm))    # A: coef = A @ y
    return fits


TREND_FIT = {code: _trend_fit(code) for code in MAIN_DEFS}


def trend_rates(code, year, draws=False):
    """Cell prevalences in `year` from the cell-level logit-linear trend; draws=True returns (NDRAW, 8) per sex."""
    out = {}
    for s in (1, 2):
        cols = []
        for j, a in enumerate(AGES):
            keep, Amat = TREND_FIT[code][(s, j)]
            if draws:
                Pb = np.column_stack([BOOT[(w, s, a, code)] for w in keep])
                Pb = np.clip(Pb, 1e-6, 1 - 1e-6)
                coef = np.log(Pb / (1 - Pb)) @ Amat.T                       # (NDRAW, 2)
                cols.append(1 / (1 + np.exp(-(coef[:, 0] + coef[:, 1] * year))))
            else:
                y = np.array([np.log(est(w, s, a, code).p / (1 - est(w, s, a, code).p)) for w in keep])
                coef = Amat @ y
                cols.append(1 / (1 + np.exp(-(coef[0] + coef[1] * year))))
        out[s] = np.column_stack(cols) if draws else np.array(cols)
    return out


# check that the closed-form WLS reproduces np.polyfit for one cell
_k, _A = TREND_FIT["D1"][(1, 0)]
_ys = np.array([np.log(est(w, 1, "50–54", "D1").p / (1 - est(w, 1, "50–54", "D1").p)) for w in _k])
_ws = np.array([(est(w, 1, "50–54", "D1").p * (1 - est(w, 1, "50–54", "D1").p) / est(w, 1, "50–54", "D1").se) ** 2 for w in _k])
qc("Trend WLS operator equals np.polyfit", "D1 males 50–54, slope", float((_A @ _ys)[1] - np.polyfit([WAVE_X[w] for w in _k], _ys, 1, w=np.sqrt(_ws))[0]), 1e-9)

TREND_DRAWS = {code: {y: trend_rates(code, y, draws=True) for y in [2023] + PROJ_YEARS} for code in MAIN_DEFS}
PROJ = []
for y in PROJ_YEARS:
    pops = {s: wpp_pop(s, y) for s in (1, 2)}
    period = "nowcast" if y <= 2026 else "projection"
    for cause in (568, 567):
        rates = {s: gbd(cause, s, 2023)[0] for s in (1, 2)}
        dr = count_draws(gbd_rate_draws(cause, 2023), pops)
        row = {"source": "GBD", "def": cause, "year": y, "period": period, "scenario": "constant 2023 rates", "n45": counts_from_rates(rates, pops),
               "n60": float(sum((rates[s][2:] * pops[s][2:]).sum() for s in (1, 2))), "n75": float(sum((rates[s][5:] * pops[s][5:]).sum() for s in (1, 2)))}
        for col in SLICES:
            CNT_DRAWS[("GBD", cause, y, "constant 2023 rates", col)] = dr[col]
            row[f"{col}_lo"], row[f"{col}_hi"] = pci(dr[col])
        row["lo"], row["hi"] = row["n45_lo"], row["n45_hi"]
        PROJ.append(row)
    for code in MAIN_DEFS:
        for scen, rates, rd in (("constant 2021–2023 rates", {s: est_vec(2026, s, code)[0] for s in (1, 2)}, {s: boot_vec(2026, s, code) for s in (1, 2)}),
                                ("2011–2023 trend continued", trend_rates(code, y), TREND_DRAWS[code][y])):
            dr = count_draws(rd, pops)
            row = {"source": "CHARLS", "def": code, "year": y, "period": period, "scenario": scen, "n45": counts_from_rates(rates, pops),
                   "n60": float(sum((rates[s][2:] * pops[s][2:]).sum() for s in (1, 2))), "n75": float(sum((rates[s][5:] * pops[s][5:]).sum() for s in (1, 2)))}
            for col in SLICES:
                CNT_DRAWS[("CHARLS", code, y, scen, col)] = dr[col]
                row[f"{col}_lo"], row[f"{col}_hi"] = pci(dr[col])
            row["lo"], row["hi"] = row["n45_lo"], row["n45_hi"]
            PROJ.append(row)
PROJ = pd.DataFrame(PROJ)
# recomputation check for one projection cell
chk = PROJ[(PROJ.source == "GBD") & (PROJ["def"] == 568) & (PROJ.year == 2035)].n45.iloc[0]
re_ = sum((gbd(568, s, 2023)[0] * wpp_pop(s, 2035)).sum() for s in (1, 2))
qc("Projection = Σ rate × WPP population", "GBD MDD constant rates, 2035", float(chk - re_), 1e-6)
_r = PROJ[(PROJ.source == "CHARLS") & (PROJ["def"] == "D1") & (PROJ.year == 2035) & (PROJ.scenario == "constant 2021–2023 rates")].iloc[0]
qc("Projection point estimate lies inside its bootstrap CI", "CHARLS D1 constant rates 2035, persons ≥50 (0 = inside)",
   max(0.0, _r.lo - _r.n45, _r.n45 - _r.hi), 1e-9)


def cnt_draws(source, code, year, scenario="observed", col="n45"):
    if source == "CHARLS" and year == 2023:
        return CNT_DRAWS[("CHARLS", code, 2023, SCEN23, col)]
    return CNT_DRAWS[(source, code, year, scenario, col)]


# three-factor decomposition (population size, age–sex structure, age–sex-specific rates), Shapley over 3! orderings.
# r1/r2 may be vectors (16,) or draw matrices (NDRAW, 16); all components then come back per draw.
def decomp3(P1, c1, r1, P2, c2, r2):
    f = lambda P, c, r: P * (c * r).sum(axis=-1)
    import itertools
    names = ["size", "structure", "rate"]
    st1, st2 = {"size": P1, "structure": c1, "rate": r1}, {"size": P2, "structure": c2, "rate": r2}
    eff = {k: 0.0 for k in names}
    for perm in itertools.permutations(names):
        cur = dict(st1)
        prev = f(cur["size"], cur["structure"], cur["rate"])
        for k in perm:
            cur[k] = st2[k]
            now = f(cur["size"], cur["structure"], cur["rate"])
            eff[k] = eff[k] + (now - prev) / 6
            prev = now
    total = f(P2, c2, r2) - f(P1, c1, r1)
    return eff, total


def struct(pops):
    v = np.concatenate([pops[1], pops[2]])
    return v.sum(), v / v.sum()


def dec_row(label, source, code, P1, c1, r1, P2, c2, r2, d1, d2):
    """Point decomposition plus percentile CIs from rate draws d1/d2 (NDRAW, 16); the population terms are fixed."""
    eff, tot = decomp3(P1, c1, r1, P2, c2, r2)
    effd, totd = decomp3(P1, c1, d1, P2, c2, d2)
    n0, n0d = P1 * (c1 * r1).sum(), P1 * (c1 * d1).sum(axis=-1)
    row = {"period": label, "source": source, "def": code, "n_start": n0, "n_end": P2 * (c2 * r2).sum(), "total": float(tot), **{k: float(v) for k, v in eff.items()}}
    row["total_lo"], row["total_hi"] = pci(totd)
    for k in ("size", "structure", "rate"):
        row[f"{k}_lo"], row[f"{k}_hi"] = pci(effd[k])
        row[f"pct_{k}_lo"], row[f"pct_{k}_hi"] = pci(100 * effd[k] / n0d)
    row["pct_total_lo"], row["pct_total_hi"] = pci(100 * totd / n0d)
    with np.errstate(invalid="ignore", divide="ignore"):
        sh = effd["structure"] / totd
    row["share_structure_lo"], row["share_structure_hi"] = pci(sh)
    qc("Decomposition draws: components sum to total", f"{label}, {source} {code}, max |residual| over draws",
       float(np.abs(effd["size"] + effd["structure"] + effd["rate"] - totd).max()), 1e-3)
    return row


DEC = []
pairs = [("2011→2023 (observed)", 2011, 2026, "gbd"), ("2023→2035 (constant rates, WPP)", 2023, 2035, "wpp")]
for label, y1, y2, src in pairs:
    if src == "gbd":
        pop1, pop2 = {s: gbd_pop(s, 2011) for s in (1, 2)}, {s: gbd_pop(s, 2023) for s in (1, 2)}
    else:
        pop1, pop2 = {s: wpp_pop(s, 2023) for s in (1, 2)}, {s: wpp_pop(s, 2035) for s in (1, 2)}
    P1, c1 = struct(pop1)
    P2, c2 = struct(pop2)
    for cause in (568, 567):
        y_start = 2011 if src == "gbd" else 2023
        r1 = np.concatenate([gbd(cause, s, y_start)[0] for s in (1, 2)])
        r2 = np.concatenate([gbd(cause, s, 2023)[0] for s in (1, 2)])
        d1 = np.hstack([gbd(cause, s, y_start)[1] for s in (1, 2)])
        d2 = np.hstack([gbd(cause, s, 2023)[1] for s in (1, 2)])
        DEC.append(dec_row(label, "GBD", cause, P1, c1, r1, P2, c2, r2, d1, d2))
    for code in MAIN_DEFS:
        w_start = 2011 if src == "gbd" else 2026
        r1 = np.concatenate([est_vec(w_start, s, code)[0] for s in (1, 2)])
        r2 = np.concatenate([est_vec(2026, s, code)[0] for s in (1, 2)])
        d1 = np.hstack([boot_vec(w_start, s, code) for s in (1, 2)])
        d2 = np.hstack([boot_vec(2026, s, code) for s in (1, 2)])
        DEC.append(dec_row(label, "CHARLS", code, P1, c1, r1, P2, c2, r2, d1, d2))
DEC = pd.DataFrame(DEC)
DEC["pct_size"] = 100 * DEC["size"] / DEC.n_start
DEC["pct_structure"] = 100 * DEC["structure"] / DEC.n_start
DEC["pct_rate"] = 100 * DEC["rate"] / DEC.n_start
DEC["share_structure"] = DEC["structure"] / DEC.total
qc("Decomposition components sum to total change", "max absolute residual over all rows",
   float((DEC[["size", "structure", "rate"]].sum(axis=1) - DEC.total).abs().max()), 1e-3)
for code in MAIN_DEFS:
    _e = DEC[(DEC.period.str.startswith("2011")) & (DEC.source == "CHARLS") & (DEC["def"] == code)].iloc[0]
    qc("2023 planning base equals decomposition end count (2021–2023 rates × GBD 2023 population)", f"CHARLS {code}, persons",
       float(CNT23[CNT23["def"] == code].n45.iloc[0] - _e.n_end), 1e-3)
_r = DEC[(DEC.period.str.startswith("2023")) & (DEC.source == "CHARLS") & (DEC["def"] == "D1")].iloc[0]
qc("Ageing share point estimate lies inside its bootstrap CI", "2023→2035 CHARLS D1 (0 = inside)",
   max(0.0, _r.share_structure_lo - _r.share_structure, _r.share_structure - _r.share_structure_hi), 1e-9)

# ============================================================================= 7. Module D: tipping-point (Rogan–Gladen) curves
# true prevalence π = (p + Sp − 1)/(Se + Sp − 1)  ⇒  for a target π_G:  Sp = (1 − p − π_G + π_G·Se)/(1 − π_G)
# CI of the required specificity: joint draws of the CHARLS apparent prevalence (PSU bootstrap) and the GBD prevalence (UI draws).
TIP = []
SE_GRID = np.linspace(0.5, 1.0, 101)
for code in ("D1", "D2", "D3"):
    r = est(2026, 3, "All ≥50", code)
    p = r.p
    pb = BOOT[(2026, 3, "All ≥50", code)]
    for cause in (568, 567):
        pw = gbd_pop(3, 2026)
        pm, pdraw = gbd(cause, 3, 2026)
        pg = float((pm * pw).sum() / pw.sum())
        pgd = (pdraw * pw[None, :]).sum(axis=1) / pw.sum()
        pg_lo, pg_hi = pci(pgd)
        sp = (1 - p - pg + pg * SE_GRID) / (1 - pg)
        spd = (1 - pb[:, None] - pgd[:, None] + pgd[:, None] * SE_GRID[None, :]) / (1 - pgd[:, None])   # (NDRAW, 101)
        sp_lo, sp_hi = pci(spd)
        for se_, sp_, l_, h_ in zip(SE_GRID, sp, sp_lo, sp_hi):
            TIP.append({"def": code, "cause_id": cause, "p_charls": p, "p_charls_lo": r.lo, "p_charls_hi": r.hi,
                        "pi_gbd": pg, "pi_gbd_lo": pg_lo, "pi_gbd_hi": pg_hi, "Se": se_, "Sp_required": sp_, "Sp_required_lo": l_, "Sp_required_hi": h_})
TIP = pd.DataFrame(TIP)
_t = TIP[(TIP["def"] == "D1") & (TIP.cause_id == 568) & np.isclose(TIP.Se, 0.9)].iloc[0]
qc("Tipping-point Sp point estimate lies inside its CI", "D1 vs GBD MDD at Se = 0.90 (0 = inside)",
   max(0.0, _t.Sp_required_lo - _t.Sp_required, _t.Sp_required - _t.Sp_required_hi), 1e-9)
# Published CES-D-10 accuracy against a clinical diagnosis, placed only on the panel whose threshold matches the published cut-off.
# Literature search 2026-11-17 (PubMed + web): no mainland-China community study of CES-D-10 against a structured diagnostic interview exists.
# Andresen 1994 reports only agreement with CES-D-20 (kappa 0.97), no Se/Sp, so it is not plotted; Irwin 1999 (Se 0.97/Sp 0.84 middle-aged,
# 1.00/0.93 aged >60) used dichotomous item scoring (cut-off 4), not the 0-30 scoring used in CHARLS; Blank 2004 does not state the cut-off in the abstract.
REF_POINTS = [
    {"def": "D2", "study": "Cheng & Chan 2005", "doi": "10.1002/gps.1314", "population": "Hong Kong, aged ≥60 y referred for psychiatric assessment (n = 398)",
     "reference": "psychiatrist diagnosis, spectrum of depressive disorders", "cutoff": 12, "Se": 0.76, "Sp": 0.55},
]
REF_TAB = pd.DataFrame(REF_POINTS)
for _r in REF_POINTS:
    _p = float(TIP.loc[TIP["def"] == _r["def"], "p_charls"].iloc[0])
    _r["pi_corrected"] = (_p + _r["Sp"] - 1) / (_r["Se"] + _r["Sp"] - 1)   # Rogan–Gladen at the published Se/Sp (negative = apparent < 1 − Sp)
REF_TAB = pd.DataFrame(REF_POINTS)

# ============================================================================= 8. Tables
# Table 1 sample characteristics by wave (weighted)
def wmean(d, col):
    m = d[col].notna()
    return np.average(d.loc[m, col], weights=d.loc[m, "weight"]) if m.any() else np.nan


def t1_ci(w, code, k=1, scale=100.0):
    """Outcome rows of Table 1: weighted estimate with 95% CI (Taylor linearisation; logit CI for proportions)."""
    r = est(w, 3, "All ≥50", code)
    if r is None or pd.isna(r.p):
        return "n/a"
    return fmt_ci(scale * r.p, scale * r.lo, scale * r.hi, k)


T1 = []
chars = [("Respondents aged ≥50 y with complete CES-D-10 (n)", lambda d, w: f"{len(d):,}"),
         ("Communities (PSUs)", lambda d, w: f"{d.communityID.nunique():,}"),
         ("Interview years", lambda d, w: "/".join(str(int(x)) for x in sorted(d.iyear.dropna().unique()))),
         ("Women (%)", lambda d, w: fmt(100 * wmean(d, "female"))),
         ("Mean age (y)", lambda d, w: fmt(wmean(d, "age"))),
         ("Aged ≥60 y (%)", lambda d, w: fmt(100 * wmean(d, "age60"))),
         ("Aged ≥75 y (%)", lambda d, w: fmt(100 * wmean(d, "age75"))),
         ("Agricultural hukou (%)", lambda d, w: fmt(100 * wmean(d, "hukou_agri"))),
         ("Any ADL limitation (%)", lambda d, w: fmt(100 * wmean(d, "adl_any"))),
         ("Self-rated health poor or very poor (%)", lambda d, w: fmt(100 * wmean(d, "srh_poor"))),
         ("Proxy interview (%)", lambda d, w: fmt(100 * wmean(d, "proxy")) if d.proxy.notna().any() else "n/a"),
         ("Mean CES-D-10 score (95% CI)", lambda d, w: t1_ci(w, "C", 2, 1.0)),
         ("CES-D-10 ≥10 (D1, % (95% CI))", lambda d, w: t1_ci(w, "D1")),
         ("CES-D-10 ≥12 (D2, % (95% CI))", lambda d, w: t1_ci(w, "D2")),
         ("CES-D-10 ≥15 (D3, % (95% CI))", lambda d, w: t1_ci(w, "D3")),
         ("Persistent ≥10 in two consecutive waves (D4, % (95% CI))", lambda d, w: t1_ci(w, "D4")),
         ("≥10 with ADL limitation (D5, % (95% CI))", lambda d, w: t1_ci(w, "D5")),
         ("Ever told by a doctor of emotional/psychiatric problem (D6, % (95% CI))", lambda d, w: t1_ci(w, "D6", 2)),
         ("≥10 without diagnosis (D7, % (95% CI))", lambda d, w: t1_ci(w, "D7"))]
for name, f in chars:
    T1.append({"Characteristic": name, **{WLAB[w]: f(A[A.wave == w], w) for w in WAVES}})
T1 = pd.DataFrame(T1)
# Table 1 outcome rows equal the weighted means computed directly
qc("Table 1 D1 cell equals direct weighted mean", "2011",
   float(abs(float(T1.loc[T1.Characteristic.str.startswith("CES-D-10 ≥10"), "2011"].iloc[0].split(" ")[0]) - round(100 * wmean(A[A.wave == 2011], "d1"), 1))), 0.051)
T1.to_csv(TAB_MAIN / "Table1_CHARLS_sample_2011_2023.csv", index=False, encoding="utf-8-sig")

# Table 2 age-standardised prevalence (%) ≥50, both sexes, by wave: CHARLS definitions and matched GBD
T2 = []
for code in list(DEFS):
    row = {"Source": "CHARLS", "Case definition": f"{code}: {DEFS[code][1]}"}
    for w in WAVES:
        r = asr_row("CHARLS", code, w, 3)
        row[WLAB[w]] = fmt_ci(100 * r.asr, 100 * r.lo, 100 * r.hi)
    T2.append(row)
for cause in (568, 567):
    row = {"Source": "GBD 2023", "Case definition": CAUSE_LONG[cause].replace("GBD ", "")}
    for w in WAVES:
        r = asr_row("GBD", cause, w, 3)
        row[WLAB[w]] = fmt_ci(100 * r.asr, 100 * r.lo, 100 * r.hi, 2)
    T2.append(row)
T2 = pd.DataFrame(T2)
T2.to_csv(TAB_MAIN / "Table2_ASR_by_definition_and_wave.csv", index=False, encoding="utf-8-sig")

# Table 3 planning base: persons ≥50 (millions) in 2023 and 2035; ratio to GBD MDD; ageing contribution
def cnt(source, code, year, scenario=None, col="n45"):
    if year <= 2023 and source == "GBD":
        return CNT[(CNT.source == "GBD") & (CNT["def"] == code) & (CNT.year == year)][col].iloc[0]
    if year == 2023:
        return CNT23[(CNT23["def"] == code)][col].iloc[0]
    if year < 2023:
        return CNT[(CNT.source == "CHARLS") & (CNT["def"] == code) & (CNT.year == year)][col].iloc[0]
    sub = PROJ[(PROJ.source == source) & (PROJ["def"] == code) & (PROJ.year == year)]
    if scenario:
        sub = sub[sub.scenario == scenario]
    return sub[col].iloc[0]


def fmt_draws(point, draws, scale=1.0, k=1):
    lo, hi = pci(draws)
    return fmt_ci(scale * point, scale * lo, scale * hi, k)


T3 = []
T3_NUM = []   # numeric companion (point, lo, hi per cell) for QC and the summary
base23 = cnt("GBD", 568, 2023)
base35 = cnt("GBD", 568, 2035)
base23_d = cnt_draws("GBD", 568, 2023)
base35_d = cnt_draws("GBD", 568, 2035, "constant 2023 rates")
for source, code, lab in [("GBD", 568, "GBD major depressive disorder"), ("GBD", 567, "GBD depressive disorders"),
                          ("CHARLS", "D1", "CHARLS D1: CES-D-10 ≥10"), ("CHARLS", "D2", "CHARLS D2: CES-D-10 ≥12"),
                          ("CHARLS", "D3", "CHARLS D3: CES-D-10 ≥15"), ("CHARLS", "D5", "CHARLS D5: ≥10 with ADL limitation"),
                          ("CHARLS", "D7", "CHARLS D7: ≥10 without diagnosis")]:
    scen = "constant 2023 rates" if source == "GBD" else "constant 2021–2023 rates"
    n23, n23_d = cnt(source, code, 2023), cnt_draws(source, code, 2023)
    n23_60, n23_60_d = cnt(source, code, 2023, col="n60"), cnt_draws(source, code, 2023, col="n60")
    ratio_cell = "1 (ref.)" if code == 568 else fmt_draws(n23 / base23, n23_d / base23_d)
    if code == "D7":
        cells = {k: "—" for k in ("n35", "chg", "share", "gap", "tr35")}
        num = {}
    else:
        n35, n35_d = cnt(source, code, 2035, scen), cnt_draws(source, code, 2035, scen)
        dec = DEC[(DEC.period.str.startswith("2023")) & (DEC.source == source) & (DEC["def"] == code)].iloc[0]
        cells = {"n35": fmt_draws(n35 / 1e6, n35_d / 1e6),
                 "chg": fmt_ci(100 * dec.total / dec.n_start, dec.pct_total_lo, dec.pct_total_hi),
                 "share": fmt_ci(100 * dec.share_structure, 100 * dec.share_structure_lo, 100 * dec.share_structure_hi, 0) if abs(dec.total) >= 0.10 * dec.n_start else "n/a",
                 "gap": "0 (ref.)" if code == 568 else fmt_draws((n35 - base35) / 1e6, (n35_d - base35_d) / 1e6),
                 "tr35": "—"}
        num = {"n35": (n35, *pci(n35_d)), "chg": (100 * dec.total / dec.n_start, dec.pct_total_lo, dec.pct_total_hi),
               "share": (dec.share_structure, dec.share_structure_lo, dec.share_structure_hi), "gap": (n35 - base35, *pci(n35_d - base35_d))}
        if source == "CHARLS":
            tr35, tr35_d = cnt("CHARLS", code, 2035, "2011–2023 trend continued"), cnt_draws("CHARLS", code, 2035, "2011–2023 trend continued")
            cells["tr35"] = fmt_draws(tr35 / 1e6, tr35_d / 1e6)
            num["tr35"] = (tr35, *pci(tr35_d))
    T3.append({"Planning base": lab,
               "2023: Persons ≥50 y (millions)": fmt_draws(n23 / 1e6, n23_d / 1e6),
               "2023: Persons ≥60 y (millions)": fmt_draws(n23_60 / 1e6, n23_60_d / 1e6),
               "2023: Ratio to GBD MDD": ratio_cell,
               "2035 (constant rates): Persons ≥50 y (millions)": cells["n35"],
               "2035 (constant rates): Change 2023–2035 on the WPP series (%)": cells["chg"],
               "2035 (constant rates): Share of increase from ageing (%)": cells["share"],
               "2035 (constant rates): Absolute gap vs GBD MDD (millions)": cells["gap"],
               "2035 (trend continued): Persons ≥50 y (millions)": cells["tr35"]})
    T3_NUM.append({"source": source, "def": code, "n23": (n23, *pci(n23_d)), "n23_60": (n23_60, *pci(n23_60_d)),
                   "ratio": (n23 / base23, *pci(n23_d / base23_d)), **num})
T3 = pd.DataFrame(T3)
T3_NUM = {(r["source"], r["def"]): r for r in T3_NUM}
qc("Table 3 2023 count equals the count frame", "CHARLS D1 persons ≥50, millions (rounded)",
   float(abs(float(T3.loc[2, "2023: Persons ≥50 y (millions)"].split(" ")[0]) - round(cnt("CHARLS", "D1", 2023) / 1e6, 1))), 0.051)
T3.to_csv(TAB_MAIN / "Table3_planning_base_2023_2035.csv", index=False, encoding="utf-8-sig")

titles = pd.DataFrame([
    {"file": "Table1_CHARLS_sample_2011_2023", "title": "Table 1 | Characteristics of CHARLS respondents aged 50 years or older with complete CES-D-10, by survey wave, 2011–2023",
     "note": "Weighted with cross-sectional individual weights adjusted for household and individual non-response; n and PSUs are unweighted. The mean CES-D-10 score and the prevalence of each case definition are given with 95% confidence intervals (Taylor linearization with communities as primary sampling units; logit-scale intervals for proportions); the other characteristics are point estimates describing the sample. ADL, activities of daily living (dressing, bathing, eating, transferring, toileting); in 2011–2018 the functional-limitation module was skipped for about 30% of respondents, who were younger and healthier, and these are coded as having no limitation. D4 requires participation in the previous wave and is therefore not defined in 2011. D6 is a lifetime self-report of a doctor's diagnosis of emotional, nervous or psychiatric problems. Proxy status is not recorded in 2013 and 2018 (n/a). The 2021–2023 wave was fielded over three years; each respondent is counted once in their response year."},
    {"file": "Table2_ASR_by_definition_and_wave", "title": "Table 2 | Age-standardized prevalence (%) of depression among adults aged 50 years or older in China by case definition and survey wave: CHARLS 2011–2023 and matched GBD 2023 estimates",
     "note": f"All rates are standardized to the same population (GBD China {STD_YEAR}, both sexes, eight 5-year groups from 50–54 to 85+). CHARLS: survey-weighted prevalence with 95% confidence intervals (Taylor linearization of the standardized sum with communities as PSUs, which retains the covariance between age groups sampled from the same communities). GBD: prevalence from IHME GBD 2023 with 95% uncertainty intervals approximated by Monte Carlo sampling of age-specific UIs assuming independence between age groups. For the 2021–2023 wave the GBD comparator is the mixture of GBD 2021, 2022 and 2023 weighted by the CHARLS interview-year distribution ({', '.join(f'{int(y)}: {100*s:.0f}%' for y, s in W6_SHARE.items())}). CES-D-10 is a symptom scale and not a diagnostic instrument; levels are not directly comparable with GBD and are shown to document the range across definitions (design §5.1)."},
    {"file": "Table3_planning_base_2023_2035", "title": "Table 3 | Numbers of adults aged 50 years or older in China meeting each depression definition in 2023 and projected to 2035 under the GBD 2023 and CHARLS age- and sex-specific rates",
     "note": f"Values are estimates with 95% intervals in parentheses. 2023 counts apply the age- and sex-specific prevalence to the GBD 2023 population (CHARLS rates are those of the 2021–2023 wave; GBD counts are the published 2023 numbers). 2035 counts apply the same rates to the UN World Population Prospects 2024 medium-variant population; they are demographic scenarios, not forecasts of risk. Because the WPP 2023 population aged ≥50 is 3% smaller than the GBD 2023 population, the change 2023–2035 and the share from ageing are both computed on the WPP series (rates × WPP 2023 → rates × WPP 2035, as in the decomposition of Fig. 5b and Supplementary Table 11) rather than from the two count columns. Intervals for CHARLS-based cells come from a design-based bootstrap of the survey ({NBOOT:,} replicates resampling communities, the primary sampling units, with replacement within each wave and recomputing every age–sex-specific prevalence and all derived quantities); intervals for GBD-based cells propagate the published 95% uncertainty intervals of each age–sex cell by lognormal Monte Carlo draws ({NDRAW:,}); ratios and gaps combine the two sets of draws, treating the sources as independent. Populations are held fixed. Share of increase from ageing is the age–sex-structure term of a three-factor decomposition (population size, age–sex structure, rates) divided by the total change (n/a when the total change is below 10% of the baseline); with constant rates the rate term is zero. Trend continued extrapolates the 2011–2023 cell-level logit trends of CHARLS prevalence to 2035 (each bootstrap replicate refits the trend) and is shown only as a bound. ref., reference category. None of these numbers is a count of clinically diagnosed patients; they are planning bases under different definitions (design §10)."},
])
titles.to_csv(TAB_MAIN / "table_titles_notes.csv", index=False, encoding="utf-8-sig")

# Supplementary tables
cw = pd.read_csv(MS / "data" / "processed" / "charls_variable_crosswalk.csv")
cw.to_csv(TAB_S / "SuppTable2_CHARLS_variable_crosswalk.csv", index=False, encoding="utf-8-sig")
S2 = EST[EST.agegrp.isin(AGES + ["All ≥50"]) & EST["def"].isin(list(DEFS) + ["C"])].copy()
S2["wave"] = S2.wave.map(WLAB)
S2["sex"] = S2.sex_id.map(SEXES)
S2 = S2[["wave", "sex", "agegrp", "def", "n", "p", "lo", "hi", "se"]].rename(columns={"p": "estimate", "lo": "ci_low", "hi": "ci_high"})
S2.to_csv(TAB_S / "SuppTable4_CHARLS_age_sex_specific_prevalence.csv", index=False, encoding="utf-8-sig")
S2g = GBA[GBA.cause_id.isin([568, 567]) & GBA.year.isin([2011, 2013, 2015, 2018, 2020, 2021, 2022, 2023])].copy()
S2g["sex"] = S2g.sex_id.map(SEXES)
S2g["cause"] = S2g.cause_id.map(CAUSE)
S2g[["cause", "year", "sex", "agegrp", "n", "pop", "prev", "prev_lo", "prev_hi"]].to_csv(TAB_S / "SuppTable3_GBD_age_sex_specific_prevalence.csv", index=False, encoding="utf-8-sig")
S4 = ASR.copy()
S4["sex"] = S4.sex_id.map(SEXES)
S4["def"] = S4["def"].map(lambda x: CAUSE.get(x, x) if isinstance(x, (int, np.integer)) else x)
S4["wave"] = S4.wave.map(lambda x: WLAB.get(x, x))
S4[["source", "def", "wave", "year", "sex", "asr", "lo", "hi", "crude", "crude_lo", "crude_hi", "n"]].to_csv(TAB_S / "SuppTable8_age_standardised_series.csv", index=False, encoding="utf-8-sig")
S5 = GRAD.copy()
S5["wave"] = S5.wave.map(WLAB)
S5["sex"] = S5.sex_id.map(SEXES)
S5 = S5.merge(OR.assign(wave=OR.wave.map(WLAB)), on=["wave", "sex_id", "def"], how="left")
S5.to_csv(TAB_S / "SuppTable5_age_gradient_tests.csv", index=False, encoding="utf-8-sig")
POOLED_GRAD.assign(sex=POOLED_GRAD.sex_id.map(SEXES)).to_csv(TAB_S / "SuppTable5b_age_gradient_pooled.csv", index=False, encoding="utf-8-sig")
S6 = SEXR.copy()
S6["def"] = S6["def"].map(lambda x: CAUSE.get(x, x) if isinstance(x, (int, np.integer)) else x)
S6["wave"] = S6.wave.map(lambda x: WLAB.get(x, x))
S6.to_csv(TAB_S / "SuppTable7_sex_ratio_by_age.csv", index=False, encoding="utf-8-sig")
S7 = TREND.copy()
S7["def"] = S7["def"].map(lambda x: CAUSE.get(x, x) if isinstance(x, (int, np.integer)) else x)
S7["sex"] = S7.sex_id.map(SEXES)
S7.to_csv(TAB_S / "SuppTable9_trend_changes.csv", index=False, encoding="utf-8-sig")
S8 = DEC.copy()
S8["def"] = S8["def"].map(lambda x: CAUSE.get(x, x) if isinstance(x, (int, np.integer)) else x)
S8.to_csv(TAB_S / "SuppTable11_decomposition.csv", index=False, encoding="utf-8-sig")
S9 = pd.concat([CNT.assign(scenario="observed"), CNT23, PROJ], ignore_index=True)
S9["def"] = S9["def"].map(lambda x: CAUSE.get(x, x) if isinstance(x, (int, np.integer)) else x)
S9.to_csv(TAB_S / "SuppTable12_counts_2011_2035.csv", index=False, encoding="utf-8-sig")
# sensitivity: D1 ASR both sexes under alternative choices — every cell "ASR (95% CI)", CI by Taylor linearisation as in Table 2
def asr_from(d, ycol, wcol, n_psu):
    """ASR (%) with linearised Taylor SE from a frame `d` using weight column `wcol` (same estimator as Table 2)."""
    dd = d[[ycol, wcol, "communityID", "agegrp"]].rename(columns={wcol: "weight"})
    if any((dd[dd.agegrp == a][ycol].notna().sum() < 20) for a in AGES):
        return np.nan, np.nan, np.nan
    asr, se = taylor_lincomb(dd, ycol, dd.agegrp.astype(str).values, dict(zip(AGES, STD_W)), n_psu)
    return 100 * asr, 100 * (asr - 1.96 * se), 100 * (asr + 1.96 * se)


SENS, SENS_NUM = [], []
for w in WAVES:
    base = asr_row("CHARLS", "D1", w, 3)
    row = {"wave": WLAB[w], "D1 base (≥10, complete items)": fmt_ci(100 * base.asr, 100 * base.lo, 100 * base.hi)}
    num = {"wave": WLAB[w], "D1 base (≥10, complete items)": (100 * base.asr, 100 * base.lo, 100 * base.hi)}
    for code, lab in [("D1pror", "≥10 with ≤2 items prorated"), ("thr8", "threshold ≥8"), ("thr12", "threshold ≥12"), ("thr15", "threshold ≥15"), ("thr16", "threshold ≥16"), ("D6ns", "non-somatic 6 items ≥6"), ("D8neg", "8 negative items ≥8 (no reversed items)")]:
        r = asr_row("CHARLS", code, w, 3)
        row[lab] = fmt_ci(100 * r.asr, 100 * r.lo, 100 * r.hi)
        num[lab] = (100 * r.asr, 100 * r.lo, 100 * r.hi)
    d = A[(A.wave == w)].copy()
    # unweighted crude: equal weights, SE still clustered by community
    d["one"] = 1.0
    p, se, _, _ = wprev(d.assign(weight=1.0), "d1", N_PSU[w])
    lo, hi = ci_logit(p, se)
    row["unweighted crude ≥10"] = fmt_ci(100 * p, 100 * lo, 100 * hi)
    num["unweighted crude ≥10"] = (100 * p, 100 * lo, 100 * hi)
    qc("Sensitivity: unweighted crude equals simple mean", WLAB[w], float(p - d.d1.mean()), 1e-9)
    # excluding proxy interviews where recorded
    if d.proxy.notna().any():
        v = asr_from(d[d.proxy == 0], "d1", "weight", N_PSU[w])
        row["excluding proxy interviews (ASR)"] = fmt_ci(*v)
        num["excluding proxy interviews (ASR)"] = v
    else:
        row["excluding proxy interviews (ASR)"] = "n/a"
        num["excluding proxy interviews (ASR)"] = (np.nan, np.nan, np.nan)
    if w == 2026:
        v = asr_from(d[d.weight_post.notna()], "d1", "weight_post", N_PSU[w])
        row["W6 post-stratification weight (ASR)"] = fmt_ci(*v)
        num["W6 post-stratification weight (ASR)"] = v
    else:
        row["W6 post-stratification weight (ASR)"] = "n/a"
        num["W6 post-stratification weight (ASR)"] = (np.nan, np.nan, np.nan)
    SENS.append(row), SENS_NUM.append(num)
SENS = pd.DataFrame(SENS)
SENS.to_csv(TAB_S / "SuppTable10_sensitivity_D1.csv", index=False, encoding="utf-8-sig")
qc("Sensitivity base column equals Table 2 D1 ASR", "2011 both sexes", float(SENS_NUM[0]["D1 base (≥10, complete items)"][0] - 100 * asr_row("CHARLS", "D1", 2011, 3).asr), 1e-9)
ASR_BOOT_CMP.to_csv(QC / "asr_se_taylor_vs_bootstrap.csv", index=False, encoding="utf-8-sig")
ITEM.to_csv(TAB_S / "SuppTable6_item_endorsement_by_age.csv", index=False, encoding="utf-8-sig")
# markdown copies of main tables
for f in TAB_MAIN.glob("Table*.csv"):
    pd.read_csv(f, encoding="utf-8-sig", dtype=str, keep_default_na=False).to_markdown(open(f.with_suffix(".md"), "w", encoding="utf-8"), index=False, disable_numparse=True)
# all supplementary tables in one workbook
with pd.ExcelWriter(TAB_S / "All_supplementary_tables_GBD_vs_CHARLS.xlsx") as xw:
    for f in sorted(TAB_S.glob("SuppTable*.csv"), key=lambda f: (int(re.match(r"SuppTable(\d+)", f.stem).group(1)), f.stem)):
        pd.read_csv(f, encoding="utf-8-sig").to_excel(xw, sheet_name=f.stem.split("_")[0], index=False)
# Table 2 cross-check against the ASR frame
r = asr_row("CHARLS", "D1", 2011, 3)
qc("Table 2 cell equals ASR frame", "D1 2011 both sexes", float(abs(float(T2.loc[0, "2011"].split(" ")[0]) - round(100 * r.asr, 1))), 0.051)

# ============================================================================= 9. Figures
def shade_periods(ax, y0=None):
    ax.axvspan(2010.5, 2023.5, color=PERIOD_COL["observed"], zorder=0, lw=0)
    ax.axvspan(2023.5, 2026.5, color=PERIOD_COL["nowcast"], zorder=0, lw=0)
    ax.axvspan(2026.5, 2035.5, color=PERIOD_COL["projection"], zorder=0, lw=0)


# ---- Figure 1: age-specific prevalence, GBD vs CHARLS definitions, by sex, three waves
def fig1():
    show = [2011, 2018, 2026]
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 5.2), sharex=True, sharey=True)
    panels, k = {}, 0
    letters = "abcdef"
    for i, s in enumerate((1, 2)):
        for j, w in enumerate(show):
            ax = axes[i, j]
            rows = []
            for code in ["D1", "D2", "D3", "D4", "D5"]:
                p, se, lo, hi = est_vec(w, s, code)
                if np.isnan(p).all():
                    continue
                ax.plot(AGE_MID, 100 * p, "-o", color=COL[code], ms=2.8, lw=1.2, label=f"CHARLS {code}")
                if code == "D1":
                    ax.fill_between(AGE_MID, 100 * lo, 100 * hi, color=COL[code], alpha=0.3, lw=0)
                for a, pp_, l, h in zip(AGES, p, lo, hi):
                    rows.append({"source": "CHARLS", "definition": code, "age_group": a, "prevalence_pct": 100 * pp_, "ci_low": 100 * l, "ci_high": 100 * h})
            for cause in (568, 567):
                p, d = gbd(cause, s, w)
                lo, hi = np.percentile(d, 2.5, axis=0), np.percentile(d, 97.5, axis=0)
                ax.plot(AGE_MID, 100 * p, LS[cause], color=COL[cause], lw=1.4, label=CAUSE_LONG[cause])
                ax.fill_between(AGE_MID, 100 * lo, 100 * hi, color=COL[cause], alpha=0.18, lw=0)
                for a, pp_, l, h in zip(AGES, p, lo, hi):
                    rows.append({"source": "GBD", "definition": CAUSE[cause], "age_group": a, "prevalence_pct": 100 * pp_, "ci_low": 100 * l, "ci_high": 100 * h})
            ax.set_yscale("log")
            ax.set_ylim(0.8, 80)
            ax.set_yticks([1, 2, 5, 10, 20, 50])
            ax.set_yticklabels(["1", "2", "5", "10", "20", "50"])
            ax.set_xticks([52.5, 62.5, 72.5, 82.5, 88])
            ax.set_xticklabels(["50–54", "60–64", "70–74", "80–84", "85+"], fontsize=7)
            ax.set_title(f"{SEXES[s]}, {WLAB[w]}", fontsize=8.5, pad=4)
            panel_letter(ax, letters[k], x=-0.18 if j == 0 else -0.08)
            panels[letters[k]] = pd.DataFrame(rows)
            k += 1
    for ax in axes[1]:
        ax.set_xlabel("Age group (years)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Prevalence (%, log scale)")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "Fig1_age_specific_prevalence_GBD_vs_CHARLS")
    source_data("Fig1_age_specific_prevalence_GBD_vs_CHARLS", panels)


fig1()


# ---- Figure 2: female-to-male ratio by age group
def fig2():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharey=True)
    panels = {}
    for ax, code, letter in zip(axes, ("D1", "D3"), "ab"):
        rows = []
        for w in WAVES:
            sub = SEXR[(SEXR.source == "CHARLS") & (SEXR["def"] == code) & (SEXR.wave == w) & SEXR.agegrp.isin(AGES)].set_index("agegrp").reindex(AGES)
            ax.plot(AGE_MID, sub.ratio, "-", color=COL["CHARLS"], alpha=0.25, lw=0.8)
            for a, r_ in zip(AGES, sub.ratio):
                rows.append({"source": "CHARLS", "series": WLAB[w], "age_group": a, "ratio": r_})
        sub = SEXR[(SEXR.source == "CHARLS") & (SEXR["def"] == code) & (SEXR.wave == "pooled") & SEXR.agegrp.isin(AGES)].set_index("agegrp").reindex(AGES)
        ax.errorbar(AGE_MID, sub.ratio, yerr=[sub.ratio - sub.lo, sub.hi - sub.ratio], fmt="o-", color=COL["CHARLS"], ms=3.5, lw=1.5, capsize=2, label=f"CHARLS {code}, 2011–2023 pooled (95% CI)")
        for a, r_, l, h in zip(AGES, sub.ratio, sub.lo, sub.hi):
            rows.append({"source": "CHARLS", "series": "pooled", "age_group": a, "ratio": r_, "ci_low": l, "ci_high": h})
        for cause in (568, 567):
            sub = SEXR[(SEXR.source == "GBD") & (SEXR["def"] == cause) & (SEXR.wave == 2026) & SEXR.agegrp.isin(AGES)].set_index("agegrp").reindex(AGES)
            ax.plot(AGE_MID, sub.ratio, LS[cause], color=COL[cause], lw=1.4, label=f"{CAUSE_LONG[cause]}, 2021–2023")
            ax.fill_between(AGE_MID, sub.lo, sub.hi, color=COL[cause], alpha=0.18, lw=0)
            for a, r_, l, h in zip(AGES, sub.ratio, sub.lo, sub.hi):
                rows.append({"source": "GBD", "series": CAUSE[cause], "age_group": a, "ratio": r_, "ci_low": l, "ci_high": h})
        ax.axhline(1, color="#999999", lw=0.7, ls="-")
        ax.set_xticks([52.5, 62.5, 72.5, 82.5, 88])
        ax.set_xticklabels(["50–54", "60–64", "70–74", "80–84", "85+"], fontsize=7)
        ax.set_xlabel("Age group (years)")
        ax.set_title({"D1": "CES-D-10 ≥10 (D1)", "D3": "CES-D-10 ≥15 (D3)"}[code], fontsize=8.5)
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    axes[0].set_ylabel("Female-to-male prevalence ratio")
    axes[0].set_ylim(0.8, 2.6)
    h, l = axes[0].get_legend_handles_labels()
    h.append(Line2D([0], [0], color=COL["CHARLS"], alpha=0.3, lw=0.8))
    l.append("CHARLS, single waves")
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "Fig2_sex_ratio_by_age")
    source_data("Fig2_sex_ratio_by_age", panels)


fig2()


# ---- Figure 3: age-standardised prevalence 2011–2023, levels and index
def fig3():
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4))
    panels = {}
    specs = [("a", 3, "level"), ("b", 3, "index"), ("c", 1, "index"), ("d", 2, "index")]
    for ax, (letter, s, mode) in zip(axes.flat, specs):
        rows = []
        ax.axvspan(2021, 2023, color="#E6E6E6", lw=0, zorder=0)   # fieldwork window of the 2021–2023 wave
        for code in MAIN_DEFS:
            sub = ASR[(ASR.source == "CHARLS") & (ASR["def"] == code) & (ASR.sex_id == s)].sort_values("year")
            base = sub.asr.iloc[0]
            y = 100 * sub.asr if mode == "level" else 100 * sub.asr / base
            err = 1.96 * 100 * sub.se / (1 if mode == "level" else base)
            ax.errorbar(sub.year, y, yerr=err, fmt="o-", color=COL[code], ms=3, lw=1.2, capsize=1.5, label=f"CHARLS {code}")
            for yr, v, e in zip(sub.year, y, err):
                rows.append({"source": "CHARLS", "definition": code, "year": yr, "value": v, "ci_low": v - e, "ci_high": v + e})
        for cause in (568, 567):
            sub = ASR[(ASR.source == "GBD") & (ASR["def"] == cause) & (ASR.sex_id == s) & (ASR.wave != 2026)].sort_values("year")
            base = sub.asr.iloc[0]
            f_ = 100 if mode == "level" else 100 / base
            ax.plot(sub.year, f_ * sub.asr, LS[cause], color=COL[cause], lw=1.4, label=CAUSE_LONG[cause])
            ax.fill_between(sub.year, f_ * sub.lo, f_ * sub.hi, color=COL[cause], alpha=0.18, lw=0)
            for yr, v, l, h in zip(sub.year, f_ * sub.asr, f_ * sub.lo, f_ * sub.hi):
                rows.append({"source": "GBD", "definition": CAUSE[cause], "year": yr, "value": v, "ci_low": l, "ci_high": h})
        if mode == "level":
            ax.set_yscale("log")
            ax.set_ylim(1, 60)
            ax.set_yticks([1, 2, 5, 10, 20, 50])
            ax.set_yticklabels(["1", "2", "5", "10", "20", "50"])
            ax.set_ylabel("Age-standardized prevalence (%, log)")
            ax.set_title("Both sexes, level", fontsize=8.5)
        else:
            ax.axhline(100, color="#999999", lw=0.7)
            ax.set_ylabel("Index (2011 = 100)")
            ax.set_title(f"{SEXES[s]}, relative to 2011", fontsize=8.5)
            ax.set_ylim(40, 130)
        ax.set_xticks([2011, 2013, 2015, 2018, 2020, W6_YEAR, 2023])
        ax.set_xticklabels(["2011", "2013", "2015", "2018", "2020", "W6", "2023"], fontsize=7)
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.04),
               title=f"W6 = CHARLS 2021–2023 wave (one survey fielded over three years; grey band), plotted at its weighted mean interview year ({W6_YEAR:.1f})", title_fontsize=7)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "Fig3_age_standardised_trend_2011_2023")
    source_data("Fig3_age_standardised_trend_2011_2023", panels)


fig3()


# ---- Figure 4: numbers of people 2011–2035
def fig4():
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.6))
    panels = {}
    for ax, col, letter, ttl in zip(axes, ("n45", "n60"), "ab", ("Aged ≥50 years", "Aged ≥60 years")):
        rows = []
        shade_periods(ax)
        lo_c, hi_c = f"{col}_lo", f"{col}_hi"

        def add_rows(src, deflab, scen, fr):
            for yr, v, l_, h_ in zip(fr.year, fr[col], fr[lo_c], fr[hi_c]):
                rows.append({"source": src, "definition": deflab, "scenario": scen, "year": yr, "persons_millions": v / 1e6, "ci_low_millions": l_ / 1e6, "ci_high_millions": h_ / 1e6})

        for cause in (568, 567):
            sub = CNT[(CNT.source == "GBD") & (CNT["def"] == cause)].sort_values("year")
            ax.fill_between(sub.year, sub[lo_c] / 1e6, sub[hi_c] / 1e6, color=COL[cause], alpha=0.15, lw=0)
            ax.plot(sub.year, sub[col] / 1e6, LS[cause], color=COL[cause], lw=1.5, label=CAUSE_LONG[cause])
            add_rows("GBD", CAUSE[cause], "observed", sub)
            pr = PROJ[(PROJ.source == "GBD") & (PROJ["def"] == cause)].sort_values("year")
            ax.fill_between([2023] + list(pr.year), [sub[lo_c].iloc[-1] / 1e6] + list(pr[lo_c] / 1e6), [sub[hi_c].iloc[-1] / 1e6] + list(pr[hi_c] / 1e6), color=COL[cause], alpha=0.12, lw=0)
            ax.plot([2023] + list(pr.year), [sub[col].iloc[-1] / 1e6] + list(pr[col] / 1e6), LS[cause], color=COL[cause], lw=1.0, alpha=0.6)
            add_rows("GBD", CAUSE[cause], "constant 2023 rates", pr)
        for code in MAIN_DEFS:
            sub = CNT[(CNT.source == "CHARLS") & (CNT["def"] == code)].sort_values("year")
            ax.errorbar(sub.year, sub[col] / 1e6, yerr=[(sub[col] - sub[lo_c]) / 1e6, (sub[hi_c] - sub[col]) / 1e6], fmt="o-", color=COL[code], ms=3, lw=1.2, capsize=1.5, label=f"CHARLS {code}")
            add_rows("CHARLS", code, "observed", sub)
            for scen, ls_, al in (("constant 2021–2023 rates", "--", 0.9), ("2011–2023 trend continued", ":", 0.9)):
                pr = PROJ[(PROJ.source == "CHARLS") & (PROJ["def"] == code) & (PROJ.scenario == scen)].sort_values("year")
                if scen.startswith("constant"):   # 95% CI band for the constant-rate scenario; the trend-scenario CI is in the source data and Supp Table 12
                    ax.fill_between([W6_YEAR] + list(pr.year), [sub[lo_c].iloc[-1] / 1e6] + list(pr[lo_c] / 1e6), [sub[hi_c].iloc[-1] / 1e6] + list(pr[hi_c] / 1e6), color=COL[code], alpha=0.15, lw=0)
                ax.plot([W6_YEAR] + list(pr.year), [sub[col].iloc[-1] / 1e6] + list(pr[col] / 1e6), ls_, color=COL[code], lw=1.0, alpha=al)
                add_rows("CHARLS", code, scen, pr)
        ax.set_xlim(2010.5, 2035.5)
        ax.set_xticks([2011, 2015, 2020, 2023, 2026, 2030, 2035])
        ax.set_xticklabels(["2011", "2015", "2020", "2023", "2026", "2030", "2035"], fontsize=7)
        ax.set_ylabel("Persons (millions)")
        ax.set_title(ttl, fontsize=8.5)
        ax.set_ylim(0, None)
        for x, t in ((2017, "observed"), (2025, "nowcast"), (2031, "projection")):
            ax.text(x, ax.get_ylim()[1] * 0.98, t, ha="center", va="top", fontsize=6.5, color="#666666")
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    h, l = axes[0].get_legend_handles_labels()
    h += [Line2D([0], [0], color="#555555", ls="--", lw=1), Line2D([0], [0], color="#555555", ls=":", lw=1)]
    l += ["constant latest rates", "trend continued"]
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "Fig4_numbers_2011_2035")
    source_data("Fig4_numbers_2011_2035", panels)


fig4()


# ---- Figure 5: decomposition
def fig5():
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.6), sharey=False)
    panels = {}
    comp_col = {"pct_size": "#BDBDBD", "pct_structure": "#E08B3A", "pct_rate": "#4292C6"}
    comp_lab = {"pct_size": "Population size", "pct_structure": "Age–sex structure (ageing)", "pct_rate": "Age–sex-specific rates"}
    for ax, period, letter in zip(axes, DEC.period.unique(), "ab"):
        sub = DEC[DEC.period == period].copy()
        sub["label"] = [CAUSE[d] if isinstance(d, (int, np.integer)) else f"CHARLS {d}" for d in sub["def"]]
        x = np.arange(len(sub))
        bw = 0.26
        for k, comp in enumerate(comp_col):
            yerr = [sub[comp] - sub[f"{comp}_lo"], sub[f"{comp}_hi"] - sub[comp]]
            ax.bar(x + (k - 1) * bw, sub[comp], bw, color=comp_col[comp], label=comp_lab[comp], edgecolor="white", lw=0.4,
                   yerr=yerr, error_kw={"elinewidth": 0.6, "capsize": 1.2, "ecolor": "#333333"})
        pct_tot = 100 * sub.total / sub.n_start
        ax.errorbar(x, pct_tot, yerr=[pct_tot - sub.pct_total_lo, sub.pct_total_hi - pct_tot], fmt="k_", ms=14, mew=1.5, elinewidth=0.6, capsize=0, label="Total change")
        ax.axhline(0, color="#333333", lw=0.7)
        ax.set_xticks(x)
        ax.set_xticklabels(sub.label, rotation=30, ha="right", fontsize=7)
        ax.set_ylabel("Change 2011→2023 (% of 2011 count)" if letter == "a" else "Change 2023→2035 (% of 2023 count)")
        ax.set_title(period, fontsize=8.5)
        panel_letter(ax, letter)
        panels[letter] = sub[["source", "label", "n_start", "n_end", "total", "total_lo", "total_hi", "size", "size_lo", "size_hi", "structure", "structure_lo", "structure_hi",
                              "rate", "rate_lo", "rate_hi", "pct_size", "pct_size_lo", "pct_size_hi", "pct_structure", "pct_structure_lo", "pct_structure_hi",
                              "pct_rate", "pct_rate_lo", "pct_rate_hi", "pct_total_lo", "pct_total_hi", "share_structure", "share_structure_lo", "share_structure_hi"]]
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "Fig5_decomposition")
    source_data("Fig5_decomposition", panels)


fig5()


# ---- Figure 6: tipping-point Se/Sp curves
def fig6():
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.5), sharey=True)
    panels = {}
    for ax, code, letter in zip(axes, ("D1", "D2", "D3"), "abc"):
        sub = TIP[TIP["def"] == code]
        for cause in (568, 567):
            t = sub[sub.cause_id == cause]
            ax.fill_between(t.Se, t.Sp_required_lo, t.Sp_required_hi, color=COL[cause], alpha=0.2, lw=0)
            ax.plot(t.Se, t.Sp_required, LS[cause], color=COL[cause], lw=1.5, label=f"target: {CAUSE_LONG[cause]}")
        ax.fill_between([0.5, 1], [0.0, 0.0], [0.5, 0.0], color="#E6E6E6", lw=0)  # below Sp = 1 − Se: Se + Sp < 1, worse than chance, uninformative
        ax.plot([0.5, 1.0], [0.5, 0.0], color="#AAAAAA", lw=0.6, ls="-")
        for rp in [r for r in REF_POINTS if r["def"] == code]:
            ax.plot(rp["Se"], rp["Sp"], "o", color="black", ms=5, label=f"{rp['study']} (Hong Kong, CES-D-10 ≥{rp['cutoff']} vs psychiatrist diagnosis)")
        if not any(r["def"] == code for r in REF_POINTS):
            ax.text(0.75, 0.62, "no eligible reference\nestimate identified\nfor this threshold", ha="center", va="center", fontsize=6, color="#777777")
        ax.set_xlim(0.5, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_xlabel("Sensitivity of the CHARLS definition")
        p, plo, phi = sub.p_charls.iloc[0], sub.p_charls_lo.iloc[0], sub.p_charls_hi.iloc[0]
        ax.set_title(f"{code}: CES-D-10 ≥{ {'D1': 10, 'D2': 12, 'D3': 15}[code] }\napparent {100*p:.1f}% ({100*plo:.1f}–{100*phi:.1f})", fontsize=8)
        panel_letter(ax, letter)
        panels[letter] = sub[["def", "cause_id", "p_charls", "p_charls_lo", "p_charls_hi", "pi_gbd", "pi_gbd_lo", "pi_gbd_hi", "Se", "Sp_required", "Sp_required_lo", "Sp_required_hi"]]
    axes[0].set_ylabel("Specificity required for\nCHARLS to equal GBD")
    panels["lit"] = REF_TAB
    h = [(Patch(color=COL[568], alpha=0.2, lw=0), Line2D([0], [0], color=COL[568], ls=LS[568], lw=1.5)),
         (Patch(color=COL[567], alpha=0.2, lw=0), Line2D([0], [0], color=COL[567], ls=LS[567], lw=1.5)),
         Line2D([0], [0], marker="o", color="black", ls="", ms=5),
         Line2D([0], [0], color="#AAAAAA", lw=0.8),
         Patch(color="#E6E6E6", lw=0)]
    l = [f"target: {CAUSE_LONG[568]} (line) with 95% interval (band)",
         f"target: {CAUSE_LONG[567]} (line) with 95% interval (band)",
         "Cheng & Chan 2005: Hong Kong, aged ≥60 y, CES-D-10 ≥12 vs psychiatrist diagnosis",
         "Se + Sp = 1 (no better than chance)",
         "Se + Sp < 1 (uninformative)"]
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.17, 1, 1))
    save(fig, "Fig6_tipping_point_Se_Sp")
    source_data("Fig6_tipping_point_Se_Sp", panels)


fig6()


# ---- Supplementary figures
def sfig1():
    fig, axes = plt.subplots(2, 6, figsize=(9.6, 4.2), sharex=True, sharey=True)
    panels, k = {}, 0
    letters = "abcdefghijkl"
    for i, s in enumerate((1, 2)):
        for j, w in enumerate(WAVES):
            ax = axes[i, j]
            rows = []
            p, se, lo, hi = est_vec(w, s, "D1")
            ax.plot(AGE_MID, 100 * p, "-o", color=COL["D1"], ms=2.5, lw=1.1)
            ax.fill_between(AGE_MID, 100 * lo, 100 * hi, color=COL["D1"], alpha=0.3, lw=0)
            for a, pp_, l, h in zip(AGES, p, lo, hi):
                rows.append({"source": "CHARLS D1", "age_group": a, "prevalence_pct": 100 * pp_, "ci_low": 100 * l, "ci_high": 100 * h})
            p, se, lo, hi = est_vec(w, s, "D3")
            ax.plot(AGE_MID, 100 * p, "-o", color=COL["D3"], ms=2.5, lw=1.1)
            for a, pp_, l, h in zip(AGES, p, lo, hi):
                rows.append({"source": "CHARLS D3", "age_group": a, "prevalence_pct": 100 * pp_, "ci_low": 100 * l, "ci_high": 100 * h})
            for cause in (568, 567):
                pg, d = gbd(cause, s, w)
                ax.plot(AGE_MID, 100 * pg, LS[cause], color=COL[cause], lw=1.2)
                for a, pp_ in zip(AGES, pg):
                    rows.append({"source": CAUSE[cause], "age_group": a, "prevalence_pct": 100 * pp_})
            ax.set_yscale("log")
            ax.set_ylim(0.8, 80)
            ax.set_yticks([1, 2, 5, 10, 20, 50])
            ax.set_yticklabels(["1", "2", "5", "10", "20", "50"])
            ax.set_xticks([52.5, 72.5, 88])
            ax.set_xticklabels(["50–54", "70–74", "85+"], fontsize=6.5)
            ax.set_title(f"{SEXES[s]}, {WLAB[w]}", fontsize=7.5, pad=3)
            panel_letter(ax, letters[k], x=-0.25 if j == 0 else -0.1)
            panels[letters[k]] = pd.DataFrame(rows)
            k += 1
    for ax in axes[:, 0]:
        ax.set_ylabel("Prevalence (%, log)")
    fig.legend([Line2D([0], [0], color=COL["D1"], marker="o", ms=3), Line2D([0], [0], color=COL["D3"], marker="o", ms=3),
                Line2D([0], [0], color=COL[568], ls="--"), Line2D([0], [0], color=COL[567], ls=":")],
               ["CHARLS D1 (≥10, 95% CI)", "CHARLS D3 (≥15)", "GBD MDD", "GBD depressive disorders"], loc="lower center", ncol=4, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.04))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "SuppFig1_age_curves_all_waves")
    source_data("SuppFig1_age_curves_all_waves", panels)


sfig1()


def sfig2():
    fig, axes = plt.subplots(2, 5, figsize=(9.2, 4.0), sharex=True, sharey=True)
    panels = {}
    for ax, (k, lab), letter in zip(axes.flat, ITEM_NAMES.items(), "abcdefghij"):
        sub = ITEM[ITEM.item == lab].set_index("agegrp").reindex(AGES)
        c = "#E08B3A" if k in SOMATIC else "#4292C6"
        ax.plot(AGE_MID, sub.pct, "-o", color=c, ms=2.8, lw=1.2)
        ax.set_title(lab + (" [somatic]" if k in SOMATIC else ""), fontsize=7)
        ax.set_xticks([52.5, 72.5, 88])
        ax.set_xticklabels(["50–54", "70–74", "85+"], fontsize=6.5)
        panel_letter(ax, letter, x=-0.2)
        panels[letter] = sub.reset_index()[["agegrp", "item", "somatic", "pct"]]
    for ax in axes[:, 0]:
        ax.set_ylabel("Item score ≥2 after\nreverse-scoring (%)")
    fig.tight_layout()
    save(fig, "SuppFig4_item_endorsement_by_age")
    source_data("SuppFig4_item_endorsement_by_age", panels)


sfig2()


def sfig3():
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.2), sharey=True)
    panels = {}
    for ax, s, letter in zip(axes, (1, 2, 3), "abc"):
        rows = []
        y = 0
        ticks, labels = [], []
        for w in WAVES:
            for code, c in (("D1", COL["D1"]), ("D6ns", "#6A51A3"), ("D3", COL["D3"])):
                r = GRAD[(GRAD.wave == w) & (GRAD.sex_id == s) & (GRAD["def"] == code)]
                if len(r) == 0:
                    continue
                r = r.iloc[0]
                ax.errorbar(r.pr, y, xerr=[[r.pr - r.pr_lo], [r.pr_hi - r.pr]], fmt="o", color=c, ms=3.5, capsize=2)
                rows.append({"wave": WLAB[w], "definition": code, "pr": r.pr, "lo": r.pr_lo, "hi": r.pr_hi, "gbd568_pr": r.gbd568_pr, "gbd567_pr": r.gbd567_pr})
                if code == "D1":
                    ax.plot(r.gbd568_pr, y, marker="|", color=COL[568], ms=10, mew=1.5)
                    ax.plot(r.gbd567_pr, y, marker="|", color=COL[567], ms=10, mew=1.5)
                y += 1
            ticks.append(y - 2)
            labels.append(WLAB[w])
            y += 0.8
        ax.axvline(1, color="#999999", lw=0.7)
        ax.set_yticks(ticks)
        ax.set_yticklabels(labels, fontsize=7)
        ax.set_xscale("log")
        ax.set_xticks([0.5, 1, 2, 4])
        ax.set_xticklabels(["0.5", "1", "2", "4"])
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlabel("Prevalence ratio, ≥75 vs 50–59 y")
        ax.set_title(SEXES[s], fontsize=8.5)
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    fig.legend([Line2D([0], [0], color=COL["D1"], marker="o", ls=""), Line2D([0], [0], color="#6A51A3", marker="o", ls=""), Line2D([0], [0], color=COL["D3"], marker="o", ls=""),
                Line2D([0], [0], color=COL[568], marker="|", ls="", ms=10), Line2D([0], [0], color=COL[567], marker="|", ls="", ms=10)],
               ["CHARLS D1 (10 items ≥10)", "CHARLS non-somatic 6 items ≥6", "CHARLS D3 (≥15)", "GBD MDD", "GBD depressive disorders"],
               loc="lower center", ncol=3, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "SuppFig3_age_gradient_by_wave")
    source_data("SuppFig3_age_gradient_by_wave", panels)


sfig3()


def sfig4():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    panels = {}
    thr_cols = {"thr8": ("≥8", "#C6DBEF"), "D1": ("≥10", "#9ECAE1"), "thr12": ("≥12", "#4292C6"), "thr15": ("≥15", "#08519C"), "thr16": ("≥16", "#08306B")}
    for ax, s, letter in zip(axes, (1, 2), "ab"):
        rows = []
        for code, (lab, c) in thr_cols.items():
            p, se, lo, hi = est_vec(2026, s, code)
            ax.plot(AGE_MID, 100 * p, "-o", color=c, ms=2.8, lw=1.2, label=f"CES-D-10 {lab}")
            for a, pp_, l, h in zip(AGES, p, lo, hi):
                rows.append({"threshold": lab, "age_group": a, "prevalence_pct": 100 * pp_, "ci_low": 100 * l, "ci_high": 100 * h})
        for cause in (568, 567):
            pg, d = gbd(cause, s, 2026)
            ax.plot(AGE_MID, 100 * pg, LS[cause], color=COL[cause], lw=1.3, label=CAUSE_LONG[cause])
            for a, pp_ in zip(AGES, pg):
                rows.append({"threshold": CAUSE[cause], "age_group": a, "prevalence_pct": 100 * pp_})
        ax.set_yscale("log")
        ax.set_ylim(0.8, 80)
        ax.set_yticks([1, 2, 5, 10, 20, 50])
        ax.set_yticklabels(["1", "2", "5", "10", "20", "50"])
        ax.set_xticks([52.5, 62.5, 72.5, 82.5, 88])
        ax.set_xticklabels(["50–54", "60–64", "70–74", "80–84", "85+"], fontsize=7)
        ax.set_title(f"{SEXES[s]}, CHARLS 2021–2023", fontsize=8.5)
        ax.set_xlabel("Age group (years)")
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    axes[0].set_ylabel("Prevalence (%, log)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    save(fig, "SuppFig2_threshold_sensitivity")
    source_data("SuppFig2_threshold_sensitivity", panels)


sfig4()


def sfig5():
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4), sharex=True)
    panels = {}
    for ax, code, letter in zip(axes.flat, ("D4", "D5", "D6", "D7"), "abcd"):
        rows = []
        for w, al in ((2018, 0.45), (2020, 0.7), (2026, 1.0)):
            for s, mk in ((1, "s"), (2, "o")):
                p, se, lo, hi = est_vec(w, s, code)
                if np.isnan(p).all():
                    continue
                ax.plot(AGE_MID, 100 * p, "-" + mk, color=COL[code], alpha=al, ms=3, lw=1.1, label=f"{SEXES[s]}, {WLAB[w]}")
                for a, pp_, l, h in zip(AGES, p, lo, hi):
                    rows.append({"definition": code, "wave": WLAB[w], "sex": SEXES[s], "age_group": a, "prevalence_pct": 100 * pp_, "ci_low": 100 * l, "ci_high": 100 * h})
        if code in ("D4", "D5", "D7"):
            for cause in (568,):
                pg, _ = gbd(cause, 3, 2026)
                ax.plot(AGE_MID, 100 * pg, LS[cause], color=COL[cause], lw=1.2, label="GBD MDD, both sexes, 2021–2023")
                for a, pp_ in zip(AGES, pg):
                    rows.append({"definition": CAUSE[cause], "wave": "2021–2023", "sex": "Both sexes", "age_group": a, "prevalence_pct": 100 * pp_})
        ax.set_title(f"{code}: {DEFS[code][1]}", fontsize=8)
        ax.set_xticks([52.5, 62.5, 72.5, 82.5, 88])
        ax.set_xticklabels(["50–54", "60–64", "70–74", "80–84", "85+"], fontsize=7)
        ax.set_ylabel("Prevalence (%)")
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    hs = [Line2D([0], [0], color="#555555", marker="s", ls="-", ms=3), Line2D([0], [0], color="#555555", marker="o", ls="-", ms=3),
          Line2D([0], [0], color="#555555", alpha=0.45), Line2D([0], [0], color="#555555", alpha=0.7), Line2D([0], [0], color="#555555", alpha=1.0),
          Line2D([0], [0], color=COL[568], ls="--")]
    fig.legend(hs, ["Males", "Females", "2018", "2020", "2021–2023", "GBD MDD, both sexes, 2021–2023"], loc="lower center", ncol=6, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.03))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    save(fig, "SuppFig5_other_definitions_by_age")
    source_data("SuppFig5_other_definitions_by_age", panels)


sfig5()


def sfig6():
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    bands = {"50–59": slice(0, 2), "60–74": slice(2, 5), "≥75": slice(5, 8)}
    series = [("GBD", 568, "constant 2023 rates", "GBD MDD, constant 2023 rates"), ("CHARLS", "D1", "constant 2021–2023 rates", "CHARLS D1, constant rates"),
              ("CHARLS", "D1", "2011–2023 trend continued", "CHARLS D1, trend"), ("CHARLS", "D3", "constant 2021–2023 rates", "CHARLS D3, constant rates")]
    rows = []
    x = np.arange(len(bands))
    bw = 0.2
    cols = [COL[568], COL["D1"], "#6BAED6", COL["D3"]]
    for k, (src, code, scen, lab) in enumerate(series):
        vals, los, his = [], [], []
        for b, sl in bands.items():
            if src == "GBD":
                rates, rd = {s: gbd(code, s, 2023)[0] for s in (1, 2)}, gbd_rate_draws(code, 2023)
            elif scen.startswith("constant"):
                rates, rd = {s: est_vec(2026, s, code)[0] for s in (1, 2)}, {s: boot_vec(2026, s, code) for s in (1, 2)}
            else:
                rates, rd = trend_rates(code, 2035), TREND_DRAWS[code][2035]
            r23, rd23 = (trend_rates(code, 2023), TREND_DRAWS[code][2023]) if scen.startswith("2011") else (rates, rd)
            n23 = sum((r23[s][sl] * gbd_pop(s, 2023)[sl]).sum() for s in (1, 2))
            n35 = sum((rates[s][sl] * wpp_pop(s, 2035)[sl]).sum() for s in (1, 2))
            d23 = sum((rd23[s][:, sl] * gbd_pop(s, 2023)[None, sl]).sum(axis=1) for s in (1, 2))
            d35 = sum((rd[s][:, sl] * wpp_pop(s, 2035)[None, sl]).sum(axis=1) for s in (1, 2))
            lo_, hi_ = pci(100 * (d35 / d23 - 1))
            vals.append(100 * (n35 / n23 - 1)), los.append(lo_), his.append(hi_)
            rows.append({"series": lab, "age_band": b, "n_2023": n23, "n_2035": n35, "change_pct": vals[-1], "ci_low": lo_, "ci_high": hi_})
        ax.bar(x + (k - 1.5) * bw, vals, bw, color=cols[k], label=lab, edgecolor="white", lw=0.4,
               yerr=[np.array(vals) - np.array(los), np.array(his) - np.array(vals)], error_kw={"elinewidth": 0.6, "capsize": 1.5, "ecolor": "#333333"})
    ax.axhline(0, color="#333333", lw=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(list(bands))
    ax.set_xlabel("Age band (years)")
    ax.set_ylabel("Change in persons 2023→2035 (%)")
    ax.legend(fontsize=7, frameon=False)
    panel_letter(ax, "a")
    fig.tight_layout()
    save(fig, "SuppFig7_projected_change_by_age_band")
    source_data("SuppFig7_projected_change_by_age_band", {"a": pd.DataFrame(rows)})


sfig6()


def sfig7():
    """Trend sensitivity: full CES-D-10 vs 8 negative items (drops the reversed 'hopeful' and 'happy') vs 6 non-somatic items."""
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.2), sharey=True)
    panels = {}
    series = [("D1", "CES-D-10 ≥10 (all 10 items)", COL["D1"]), ("D8neg", "8 negative items ≥8", "#E08B3A"), ("D6ns", "6 non-somatic items ≥6", "#6A51A3")]
    for ax, s, letter in zip(axes, (3, 1, 2), "abc"):
        rows = []
        for code, lab, c in series:
            sub = ASR[(ASR.source == "CHARLS") & (ASR["def"] == code) & (ASR.sex_id == s)].sort_values("year")
            base = sub.asr.iloc[0]
            idx = 100 * sub.asr / base
            err = 1.96 * 100 * sub.se / base
            ax.errorbar(sub.year, idx, yerr=err, fmt="o-", color=c, ms=3, lw=1.2, capsize=1.5, label=lab)
            for yr, v, e, a_ in zip(sub.year, idx, err, sub.asr):
                rows.append({"definition": code, "year": yr, "asr_pct": 100 * a_, "index_2011_100": v, "ci_low": v - e, "ci_high": v + e})
        ax.axhspan(2021, 2023, color="#E6E6E6", lw=0, zorder=0) if False else ax.axvspan(2021, 2023, color="#E6E6E6", lw=0, zorder=0)
        ax.axhline(100, color="#999999", lw=0.7)
        ax.set_xticks([2011, 2013, 2015, 2018, 2020, W6_YEAR])
        ax.set_xticklabels(["2011", "2013", "2015", "2018", "2020", "W6"], fontsize=7)
        ax.set_title(SEXES[s], fontsize=8.5)
        panel_letter(ax, letter)
        panels[letter] = pd.DataFrame(rows)
    axes[0].set_ylabel("Age-standardized prevalence, index (2011 = 100)")
    axes[0].set_ylim(60, 120)
    hl = {}
    for a in axes:
        for h_, l_ in zip(*a.get_legend_handles_labels()):
            hl.setdefault(l_, h_)
    panels["lit"] = REF_TAB
    h, l = list(hl.values()), list(hl.keys())
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "SuppFig6_trend_sensitivity_item_sets")
    source_data("SuppFig6_trend_sensitivity_item_sets", panels)


sfig7()

# ============================================================================= 10. Key numbers for legends / summary
def R(k, v):
    RES[k] = v
    return v


for s in (1, 2, 3):
    for code in ("D1", "D3"):
        r = POOLED_GRAD[(POOLED_GRAD.sex_id == s) & (POOLED_GRAD["def"] == code)].iloc[0]
        R(f"pr_pooled_{code}_{s}", (r.pr, r.pr_lo, r.pr_hi, r.gbd568_pr_mean, r.gbd567_pr_mean, r.gbd568_pr_lo, r.gbd568_pr_hi, r.gbd567_pr_lo, r.gbd567_pr_hi))
    r = POOLED_GRAD[(POOLED_GRAD.sex_id == s) & (POOLED_GRAD["def"] == "D6ns")].iloc[0]
    R(f"pr_pooled_D6ns_{s}", (r.pr, r.pr_lo, r.pr_hi))
for w in (2011, 2026):
    for s in (1, 2):
        p, _, _, _ = est_vec(w, s, "D1")
        R(f"d1_{w}_{s}", p)
        R(f"gbd568_{w}_{s}", gbd(568, s, w)[0])
sr = SEXR[(SEXR.source == "CHARLS") & (SEXR["def"] == "D1") & (SEXR.wave == "pooled")].set_index("agegrp")
R("sexratio_D1_5054", (sr.loc["50–54", "ratio"], sr.loc["50–54", "lo"], sr.loc["50–54", "hi"]))
R("sexratio_D1_85", (sr.loc["85+", "ratio"], sr.loc["85+", "lo"], sr.loc["85+", "hi"]))
R("sexratio_D1_all", (sr.loc["All ≥50", "ratio"], sr.loc["All ≥50", "lo"], sr.loc["All ≥50", "hi"]))
g = SEXR[(SEXR.source == "GBD") & (SEXR["def"] == 568) & (SEXR.wave == 2026)].set_index("agegrp")
R("gbd_sexratio_range", (g.loc[AGES, "ratio"].min(), g.loc[AGES, "ratio"].max()))
for code in MAIN_DEFS:
    r = TREND[(TREND.source == "CHARLS") & (TREND["def"] == code) & (TREND.sex_id == 3) & (TREND["from"] == "2011") & (TREND["to"] == "2021–2023")].iloc[0]
    R(f"trend_{code}", (r.asr_from, r.asr_to, r.rel_change, r.rel_lo, r.rel_hi))
    r = TREND[(TREND.source == "CHARLS") & (TREND["def"] == code) & (TREND.sex_id == 3) & (TREND["from"] == "2018") & (TREND["to"] == "2020")].iloc[0]
    R(f"trend1820_{code}", (r.rel_change, r.rel_lo, r.rel_hi))
for cause in (568, 567):
    r = TREND[(TREND.source == "GBD") & (TREND["def"] == cause) & (TREND.sex_id == 3) & (TREND["from"] == "2011") & (TREND["to"] == "2021–2023")].iloc[0]
    R(f"trend_{cause}", (r.asr_from, r.asr_to, r.rel_change, r.rel_lo, r.rel_hi))
    r = TREND[(TREND.source == "GBD") & (TREND["def"] == cause) & (TREND.sex_id == 3) & (TREND["from"] == "2018") & (TREND["to"] == "2020")].iloc[0]
    R(f"trend1820_{cause}", (r.rel_change, r.rel_lo, r.rel_hi))
R("pop45_2011", gbd_pop(3, 2011).sum())
R("pop45_2023", gbd_pop(3, 2023).sum())
R("pop45_2035", wpp_pop(3, 2035).sum())
R("pop60_share_2023", gbd_pop(3, 2023)[2:].sum() / gbd_pop(3, 2023).sum())
R("pop60_share_2035", wpp_pop(3, 2035)[2:].sum() / wpp_pop(3, 2035).sum())
for src, code in [("GBD", 568), ("GBD", 567), ("CHARLS", "D1"), ("CHARLS", "D2"), ("CHARLS", "D3"), ("CHARLS", "D5"), ("CHARLS", "D7")]:
    R(f"n2023_{code}", cnt(src, code, 2023))
    R(f"n2023ci_{code}", T3_NUM[(src, code)]["n23"][1:])
    R(f"ratio2023_{code}", T3_NUM[(src, code)]["ratio"])
    if code != "D7":
        R(f"n2035_{code}", cnt(src, code, 2035, "constant 2023 rates" if src == "GBD" else "constant 2021–2023 rates"))
        R(f"n2035ci_{code}", T3_NUM[(src, code)]["n35"][1:])
        R(f"chg2335_{code}", T3_NUM[(src, code)]["chg"])
        d1 = DEC[(DEC.period.str.startswith("2011")) & (DEC["def"] == code)].iloc[0]
        d2 = DEC[(DEC.period.str.startswith("2023")) & (DEC["def"] == code)].iloc[0]
        R(f"dec1123_{code}", (d1.total, d1["size"], d1.structure, d1.rate, d1.share_structure, d1.share_structure_lo, d1.share_structure_hi, d1.total_lo, d1.total_hi, d1.structure_lo, d1.structure_hi))
        R(f"dec2335_{code}", (d2.total, d2["size"], d2.structure, d2.share_structure, d2.share_structure_lo, d2.share_structure_hi))
        if src == "CHARLS":
            R(f"tr2035_{code}", T3_NUM[(src, code)]["tr35"])
R("n2011_568", cnt("GBD", 568, 2011))
R("n2011_D1", CNT[(CNT.source == "CHARLS") & (CNT["def"] == "D1") & (CNT.wave == 2011)].n45.iloc[0])
for code in ("D1", "D2", "D3"):
    for cause in (568, 567):
        t = TIP[(TIP["def"] == code) & (TIP.cause_id == cause)]
        t90 = t[np.isclose(t.Se, 0.9)].iloc[0]
        R(f"tip_{code}_{cause}", (t.p_charls.iloc[0], t.pi_gbd.iloc[0], t90.Sp_required, t90.Sp_required_lo, t90.Sp_required_hi, t.p_charls_lo.iloc[0], t.p_charls_hi.iloc[0], t.pi_gbd_lo.iloc[0], t.pi_gbd_hi.iloc[0]))
R("asr_boot_ratio", (ASR_BOOT_CMP.ratio_bootstrap_to_linearised.min(), ASR_BOOT_CMP.ratio_bootstrap_to_linearised.max()))
R("asr_indep_ratio", (ASR_BOOT_CMP.ratio_linearised_to_independent.min(), ASR_BOOT_CMP.ratio_linearised_to_independent.max()))
R("asr_2026_D1", asr_row("CHARLS", "D1", 2026, 3).asr)
for code in ("D1", "D8neg", "D6ns"):
    for a_, b_ in [("2011", "2013"), ("2013", "2015"), ("2011", "2021–2023"), ("2018", "2020")]:
        r = TREND[(TREND.source == "CHARLS") & (TREND["def"] == code) & (TREND.sex_id == 3) & (TREND["from"] == a_) & (TREND["to"] == b_)].iloc[0]
        R(f"tr_{code}_{a_}_{b_}", (r.asr_from, r.asr_to, r.rel_change, r.rel_lo, r.rel_hi))
    r = POOLED_GRAD[(POOLED_GRAD.sex_id == 3) & (POOLED_GRAD["def"] == code)].iloc[0]
    R(f"grad_{code}", (r.pr, r.pr_lo, r.pr_hi))
R("asr_2026_568", asr_row("GBD", 568, 2026, 3).asr)
R("asr_2026_567", asr_row("GBD", 567, 2026, 3).asr)
R("w6_share", dict(W6_SHARE))
R("n_personwaves", int(SAMPLE.sum()))
R("sample", dict(SAMPLE))
R("or_D1_pooled", {s: tuple(OR_POOLED[(OR_POOLED.sex_id == s) & (OR_POOLED["def"] == "D1")].iloc[0][["or_10y", "lo", "hi"]]) for s in (1, 2, 3)})
# GBD ratio per 10 years averaged over the six matched years, UI from the draws averaged the same way
R("gslope_568", {s: (GSLOPE[(GSLOPE.cause_id == 568) & (GSLOPE.sex_id == s)].ratio_10y.mean(),
                     *pci(np.mean([GSLOPE_DRAWS[(568, w, s)] for w in WAVES], axis=0))) for s in (1, 2, 3)})

# ============================================================================= 11. Legends
def pct(x, k=1):
    return f"{100 * x:.{k}f}%"


def m_(x):
    return f"{x / 1e6:.1f} million"


def mci(key):
    """'148.5 million (142.9–154.2)' from RES[n…_key] and RES[n…ci_key]."""
    stem, code = key.split("_", 1)
    v, (lo, hi) = RES[f"{stem}_{code}"], RES[f"{stem}ci_{code}"]
    return f"{v / 1e6:.1f} million ({lo / 1e6:.1f}–{hi / 1e6:.1f})"


def sh_(t, i):
    """ageing share with CI from a dec tuple: '16% (13–19)'."""
    return f"{fmt(100*t[i], 0)}% ({fmt(100*t[i+1], 0)} to {fmt(100*t[i+2], 0)})"


pr1 = RES["pr_pooled_D1_3"]
pr3 = RES["pr_pooled_D3_3"]
prm, prf = RES["pr_pooled_D1_1"], RES["pr_pooled_D1_2"]
prns = RES["pr_pooled_D6ns_3"]
sr45, sr85, srall = RES["sexratio_D1_5054"], RES["sexratio_D1_85"], RES["sexratio_D1_all"]
gsr = RES["gbd_sexratio_range"]
t1, t3, t568, t567 = RES["trend_D1"], RES["trend_D3"], RES["trend_568"], RES["trend_567"]
tt1, tt568 = RES["trend1820_D1"], RES["trend1820_568"]
d568, dD1, dD3 = RES["dec1123_568"], RES["dec1123_D1"], RES["dec1123_D3"]
e568, eD1, eD3 = RES["dec2335_568"], RES["dec2335_D1"], RES["dec2335_D3"]
tipD1, tipD2, tipD3 = RES["tip_D1_568"], RES["tip_D2_568"], RES["tip_D3_568"]
share_txt = ", ".join(f"{int(y)}: {100*s:.0f}%" for y, s in W6_SHARE.items())
LEG = f"""# Figure Legends — Depression among adults aged 50 years or older in China: age structure, trends and population scale in GBD 2023 versus CHARLS 2011–2023

> Nature Medicine-style figure legends generated by `09_代码与质控_Code_QC/01_run_analysis.py`. Abbreviations: **ASR** age-standardized rate (standard: GBD China {STD_YEAR}, both sexes, ages 50–54 to 85+ in eight 5-year groups); **CES-D-10** 10-item Center for Epidemiologic Studies Depression scale (0–30); **CHARLS** China Health and Retirement Longitudinal Study; **CI** confidence interval; **GBD** Global Burden of Disease Study 2023 (IHME); **MDD** major depressive disorder; **PR** prevalence ratio; **PSU** primary sampling unit; **UI** uncertainty interval; **WPP** United Nations World Population Prospects 2024. Data: {DATA_VERSION}. CHARLS estimates use the cross-sectional individual weight with household and individual non-response adjustment; standard errors use Taylor linearization with communities as PSUs ({N_PSU.min()}–{N_PSU.max()} PSUs per wave). CHARLS analytic sample: respondents aged ≥50 years with all ten CES-D-10 items and a weight ({', '.join(f'{WLAB[w]}: {int(SAMPLE[w]):,}' for w in WAVES)}; {RES['n_personwaves']:,} person-waves). Case definitions (design §5.1): D1 CES-D-10 ≥10; D2 ≥12; D3 ≥15; D4 ≥10 in two consecutive waves; D5 ≥10 with any ADL limitation; D6 self-reported doctor diagnosis of emotional, nervous or psychiatric problems; D7 ≥10 without such a diagnosis. GBD prevalence is point prevalence from the GBD 2023 results tool; its UIs for aggregated groups and ASRs are approximated by Monte Carlo sampling of age-specific UIs assuming independence between age groups ({NDRAW:,} draws). **Intervals.** Every CHARLS estimate carries a 95% CI: age–sex-specific prevalences, ASRs (including the sensitivity-analysis ASRs), prevalence ratios and their changes use Taylor linearization with communities as PSUs (the ASR is linearized as one standardized sum, so the covariance between age groups sampled from the same communities is retained); estimates pooled across waves (prevalence ratios, female-to-male ratios, odds ratios) are linearized jointly across waves, because the waves share the same communities and many respondents; counts of persons, projections, the decomposition and the tipping-point curves use a design-based bootstrap ({NBOOT:,} replicates resampling communities with replacement within each wave, Rao–Wu rescaling, all age–sex-specific prevalences and every derived quantity recomputed per replicate, 2.5th–97.5th percentiles); where a quantity combines CHARLS and GBD, the bootstrap replicates are paired with the GBD draws, treating the two sources as independent; populations are held fixed. The bootstrap SE of the D1 ASR was {RES['asr_boot_ratio'][0]:.2f}–{RES['asr_boot_ratio'][1]:.2f} times the linearized Taylor SE across waves, confirming the two approaches agree (`qc/asr_se_taylor_vs_bootstrap.csv`; a formula treating age cells as independent would understate the SE by about {100*(1-1/RES['asr_indep_ratio'][0]):.0f}–{100*(1-1/RES['asr_indep_ratio'][1]):.0f}%). The 2021–2023 CHARLS wave is compared with the mixture of GBD 2021–2023 weighted by the CHARLS interview-year distribution ({share_txt}) and plotted at {W6_YEAR:.1f}. Colours: CHARLS definitions in blues/teal (D1 light blue, D2 mid blue, D3 dark blue, D4 purple, D5 teal); GBD MDD red dashed; GBD depressive disorders orange dotted. CES-D-10 is a symptom scale; levels are not clinical prevalence and are compared only for structure and trend unless stated. Source data for each figure are in `07_源数据_SourceData/<Figure>_SourceData.xlsx` (and `.csv`); panels a, b, c… correspond to worksheets of the same name.

---

## Figure 1 | Age-specific prevalence of depression among adults aged 50 years or older in China by sex: CHARLS case definitions versus GBD 2023, in 2011, 2018 and 2021–2023.
*File:* `Fig1_age_specific_prevalence_GBD_vs_CHARLS.pdf` · *Source data:* `Fig1_SourceData.xlsx`

**a**–**c**, Males in 2011 (**a**), 2018 (**b**) and 2021–2023 (**c**). **d**–**f**, Females, same years. Points and lines are survey-weighted CHARLS prevalence for D1–D5 (D4 from 2013 onwards); shading around D1 is the 95% CI. Dashed red and dotted orange lines are GBD MDD and GBD depressive disorders with 95% UI bands. *Scale:* logarithmic y axis so that both sources are visible; the slopes, not the levels, are the object of comparison.

**Note.** Pooling 2011–2023 by inverse-variance weighting, the CHARLS D1 prevalence ratio for ages ≥75 versus 50–59 years was {pr1[0]:.2f} (95% CI {pr1[1]:.2f}–{pr1[2]:.2f}; males {prm[0]:.2f} ({prm[1]:.2f}–{prm[2]:.2f}), females {prf[0]:.2f} ({prf[1]:.2f}–{prf[2]:.2f})), and {pr3[0]:.2f} ({pr3[1]:.2f}–{pr3[2]:.2f}) for D3, whereas the same ratio in GBD was {pr1[3]:.2f} (95% UI {pr1[5]:.2f}–{pr1[6]:.2f}) for MDD and {pr1[4]:.2f} ({pr1[7]:.2f}–{pr1[8]:.2f}) for depressive disorders. Restricting the scale to the six non-somatic items gave a pooled ratio of {prns[0]:.2f} ({prns[1]:.2f}–{prns[2]:.2f}). In survey-weighted logistic regression the pooled D1 odds ratio per 10 years of age was {RES['or_D1_pooled'][3][0]:.2f} ({RES['or_D1_pooled'][3][1]:.2f}–{RES['or_D1_pooled'][3][2]:.2f}), against a GBD MDD prevalence ratio per 10 years of {RES['gslope_568'][3][0]:.3f} ({RES['gslope_568'][3][1]:.3f}–{RES['gslope_568'][3][2]:.3f}). Source data: `Fig1_SourceData.xlsx` (sheets a–f).

---

## Figure 2 | Female-to-male prevalence ratio by age group: CHARLS 2011–2023 versus GBD 2023.
*File:* `Fig2_sex_ratio_by_age.pdf` · *Source data:* `Fig2_SourceData.xlsx`

**a**, CES-D-10 ≥10 (D1). **b**, CES-D-10 ≥15 (D3). Thin blue lines are single CHARLS waves; blue points with 95% CIs are the inverse-variance pooled ratio across the six waves. GBD ratios (2021–2023 mixture) are shown with 95% UI bands. The horizontal line marks a ratio of 1.

**Note.** The pooled CHARLS D1 female-to-male ratio was {srall[0]:.2f} ({srall[1]:.2f}–{srall[2]:.2f}) overall, {sr45[0]:.2f} ({sr45[1]:.2f}–{sr45[2]:.2f}) at 50–54 years and {sr85[0]:.2f} ({sr85[1]:.2f}–{sr85[2]:.2f}) at ≥85 years, whereas the GBD MDD ratio ranged only from {gsr[0]:.2f} to {gsr[1]:.2f} across age groups. Source data: `Fig2_SourceData.xlsx` (sheets a, b).

---

## Figure 3 | Age-standardized prevalence of depression among adults aged 50 years or older in China, 2011–2023: CHARLS case definitions and GBD 2023.
*File:* `Fig3_age_standardised_trend_2011_2023.pdf` · *Source data:* `Fig3_SourceData.xlsx`

**a**, Levels (both sexes, log scale). **b**–**d**, The same series indexed to 2011 = 100 for both sexes (**b**), males (**c**) and females (**d**). CHARLS points carry 95% CIs; GBD lines carry 95% UI bands (annual values, through 2023). The 2021–2023 CHARLS wave is one survey fielded over three years (grey band; 68% of interviews in 2021) and is plotted once at its weighted mean interview year; it is not split by calendar year because the 2022–2023 interviews are the harder-to-reach remainder of the sample. All series use the same standard population.

**Note.** Between 2011 and 2021–2023 the CHARLS D1 ASR changed from {pct(t1[0])} to {pct(t1[1])} ({100*t1[2]:+.1f}%, 95% CI {100*t1[3]:+.1f} to {100*t1[4]:+.1f}) and D3 from {pct(t3[0])} to {pct(t3[1])} ({100*t3[2]:+.1f}%, {100*t3[3]:+.1f} to {100*t3[4]:+.1f}), whereas GBD MDD rose from {pct(t568[0], 2)} to {pct(t568[1], 2)} ({100*t568[2]:+.1f}%, UI {100*t568[3]:+.1f} to {100*t568[4]:+.1f}) and GBD depressive disorders from {pct(t567[0], 2)} to {pct(t567[1], 2)} ({100*t567[2]:+.1f}%, {100*t567[3]:+.1f} to {100*t567[4]:+.1f}). Between 2018 and 2020 the change was {100*tt1[0]:+.1f}% (CI {100*tt1[1]:+.1f} to {100*tt1[2]:+.1f}) in CHARLS D1 and {100*tt568[0]:+.1f}% (UI {100*tt568[1]:+.1f} to {100*tt568[2]:+.1f}) in GBD MDD. Source data: `Fig3_SourceData.xlsx` (sheets a–d).

---

## Figure 4 | Numbers of adults aged 50 years or older (a) and 60 years or older (b) in China meeting each depression definition, 2011–2023 observed and 2024–2035 under constant and trend scenarios.
*File:* `Fig4_numbers_2011_2035.pdf` · *Source data:* `Fig4_SourceData.xlsx`

Observed period (grey): CHARLS age- and sex-specific prevalence applied to the GBD population of the matched year, with 95% CIs (error bars; PSU bootstrap); GBD counts are published numbers (annual) with 95% UI bands. Nowcast 2024–2026 (orange) and projection 2027–2035 (blue) apply either the latest rates (GBD 2023; CHARLS 2021–2023; dashed, with 95% interval bands) or the 2011–2023 CHARLS cell-level logit trend (dotted; its 95% CI is given in the source data and Supplementary Table 12 to keep the panels legible) to the UN WPP 2024 medium-variant population, which is held fixed. These are demographic scenarios, not forecasts of risk.

**Note.** In 2023 the GBD MDD count was {mci('n2023_568')} ({mci('n2023_567')} for depressive disorders); applying the 2021–2023 CHARLS rates to the GBD 2023 population gives {mci('n2023_D1')} (D1), {mci('n2023_D2')} (D2), {mci('n2023_D3')} (D3) and {mci('n2023_D5')} (D5) (the plotted 2021–2023 point uses the population of the mixture year, 2021.4, and is therefore 4% lower), that is {RES['ratio2023_D1'][0]:.1f} ({RES['ratio2023_D1'][1]:.1f}–{RES['ratio2023_D1'][2]:.1f}) times the GBD MDD count for D1 and {RES['ratio2023_D3'][0]:.1f} ({RES['ratio2023_D3'][1]:.1f}–{RES['ratio2023_D3'][2]:.1f}) times for D3. With constant rates the 2035 numbers are {mci('n2035_568')} (GBD MDD) and {mci('n2035_D1')} (D1), {mci('n2035_D3')} (D3); with the 2011–2023 trend continued, {RES['tr2035_D1'][0]/1e6:.1f} million ({RES['tr2035_D1'][1]/1e6:.1f}–{RES['tr2035_D1'][2]/1e6:.1f}) for D1. Source data: `Fig4_SourceData.xlsx` (sheets a, b).

---

## Figure 5 | Decomposition of the change in the number of adults aged 50 years or older with depression into population size, age–sex structure and age–sex-specific rates, by data source and definition.
*File:* `Fig5_decomposition.pdf` · *Source data:* `Fig5_SourceData.xlsx`

**a**, 2011→2023 (GBD populations; CHARLS rates of 2011 and 2021–2023). **b**, 2023→2035 with constant rates (WPP 2024 population), so the rate term is zero by construction. Bars are the three Shapley-symmetric components (Das Gupta) expressed as a percentage of the baseline count, with 95% intervals (CHARLS: PSU bootstrap of the rates; GBD: UI draws; populations fixed); black ticks are the total change with its interval. The share of the total change attributable to the age–sex structure (ageing), with 95% intervals, is given in Table 3 and Supplementary Table 11 (source data: column share_structure).

**Note.** For 2011→2023, ageing contributed {sh_(d568, 4)} of the GBD MDD increase ({d568[2]/1e6:+.2f} million ({d568[9]/1e6:+.2f} to {d568[10]/1e6:+.2f}) of {d568[0]/1e6:+.2f} million ({d568[7]/1e6:+.2f} to {d568[8]/1e6:+.2f})) but {sh_(dD1, 4)} ({dD1[2]/1e6:+.2f} million ({dD1[9]/1e6:+.2f} to {dD1[10]/1e6:+.2f}) of {dD1[0]/1e6:+.2f} million ({dD1[7]/1e6:+.2f} to {dD1[8]/1e6:+.2f})) under CHARLS D1 and {sh_(dD3, 4)} under D3. For 2023→2035 with constant rates, ageing accounts for {sh_(e568, 3)} of the GBD MDD change versus {sh_(eD1, 3)} (D1) and {sh_(eD3, 3)} (D3). Source data: `Fig5_SourceData.xlsx` (sheets a, b).

---

## Figure 6 | Tipping-point analysis: the combinations of sensitivity and specificity under which the CHARLS screening prevalence would equal the GBD prevalence.
*File:* `Fig6_tipping_point_Se_Sp.pdf` · *Source data:* `Fig6_SourceData.xlsx`

**a**–**c**, D1 (**a**), D2 (**b**) and D3 (**c**), adults aged ≥50 years, both sexes, CHARLS 2021–2023 versus GBD 2021–2023 (crude). Curves (dashed, MDD; dotted, depressive disorders) solve the Rogan–Gladen relation π = (p + Sp − 1)/(Se + Sp − 1) for the specificity required at each sensitivity so that the corrected prevalence π equals the GBD MDD (red) or depressive-disorder (orange) prevalence; shaded bands are 95% intervals obtained by pairing the PSU-bootstrap replicates of the CHARLS apparent prevalence p with the GBD UI draws of π; the grey line marks Se + Sp = 1 (a test no better than chance) and the grey triangle below it (Se + Sp < 1) is uninformative. Panel titles give the apparent prevalence with its 95% CI. The circle in **b** is the only published accuracy estimate of the Chinese CES-D-10 against a clinical diagnosis at a matching threshold: ≥12, sensitivity 0.76 and specificity 0.55 against psychiatrist diagnosis across the spectrum of depressive disorders, in 398 Hong Kong adults aged ≥60 years referred for psychiatric assessment (Cheng & Chan 2005); it is shown for context, because its referral setting and diagnostic target differ from the community MDD comparison. No eligible reference estimate was identified for thresholds 10 (**a**) or 15 (**c**).

**Note.** With apparent prevalence {pct(tipD1[0])} (95% CI {pct(tipD1[5])}–{pct(tipD1[6])}) for D1 against GBD MDD {pct(tipD1[1], 2)} (UI {pct(tipD1[7], 2)}–{pct(tipD1[8], 2)}), equality at a sensitivity of 0.90 would require a specificity of {tipD1[2]:.3f} ({tipD1[3]:.3f}–{tipD1[4]:.3f}); for D2 ({pct(tipD2[0])}, {pct(tipD2[5])}–{pct(tipD2[6])}) {tipD2[2]:.3f} ({tipD2[3]:.3f}–{tipD2[4]:.3f}) and for D3 ({pct(tipD3[0])}, {pct(tipD3[5])}–{pct(tipD3[6])}) {tipD3[2]:.3f} ({tipD3[3]:.3f}–{tipD3[4]:.3f}). At the Hong Kong estimate the Rogan–Gladen corrected D2 prevalence would fall below zero, because the apparent prevalence ({pct(tipD2[0])}) is lower than the false-positive rate implied by Sp = 0.55 (45%); that is, accuracy measured in a referred clinical sample, where non-cases carry many symptoms, does not transfer to a community sample. A literature search (PubMed and web, November 2026) identified no eligible validation study of CES-D-10 against a structured diagnostic interview in community-dwelling mainland Chinese adults aged ≥45 or ≥50 years, so no Bayesian Rogan–Gladen correction was fitted (design §7 D); the figure therefore bounds, rather than estimates, the level difference. Source data: `Fig6_SourceData.xlsx` (sheets a–c; sheet lit, literature point).

---

## Supplementary Fig. 1 | Age-specific prevalence of CES-D-10 ≥10 (D1) and ≥15 (D3) by sex in all six CHARLS waves, with GBD MDD and depressive disorders of the matched year.
*File:* `SuppFig1_age_curves_all_waves.pdf` · *Source data:* `SuppFig1_SourceData.xlsx`

**a**–**f**, Males, 2011 to 2021–2023; **g**–**l**, females. Shading, 95% CI of D1. Logarithmic y axis.

## Supplementary Fig. 2 | Age-specific prevalence in CHARLS 2021–2023 under alternative CES-D-10 thresholds (≥8, ≥10, ≥12, ≥15, ≥16) with GBD comparators.
*File:* `SuppFig2_threshold_sensitivity.pdf` · *Source data:* `SuppFig2_SourceData.xlsx`

**a**, Males; **b**, females. Logarithmic y axis.

## Supplementary Fig. 3 | Prevalence ratio for ages ≥75 versus 50–59 years by wave and sex: CHARLS D1, the six-item non-somatic version, D3, and GBD.
*File:* `SuppFig3_age_gradient_by_wave.pdf` · *Source data:* `SuppFig3_SourceData.xlsx`

**a**, Males; **b**, females; **c**, both sexes. Points with 95% CIs are CHARLS; vertical ticks are the GBD ratios of the matched year (red MDD, orange depressive disorders). Logarithmic x axis.

## Supplementary Fig. 4 | Proportion with an item score ≥2 after reverse-scoring, by CES-D-10 item and age group, CHARLS 2011–2023 pooled.
*File:* `SuppFig4_item_endorsement_by_age.pdf` · *Source data:* `SuppFig4_SourceData.xlsx`

**a**–**j**, One panel per item; somatic items (trouble keeping mind on tasks, everything an effort, restless sleep, could not get going) in orange, affective items in blue. For the eight negatively worded items a score ≥2 means the symptom on ≥3 days of the past week; for the two positively worded items (hopeful, happy) it means hopefulness or happiness on ≤2 days. Waves are weighted equally. Used to judge whether the age gradient is driven by somatic items (design §7 C3).

## Supplementary Fig. 5 | Age-specific prevalence of the persistence, functional-limitation, diagnosis and unrecognized definitions (D4–D7) by sex, CHARLS 2018, 2020 and 2021–2023.
*File:* `SuppFig5_other_definitions_by_age.pdf` · *Source data:* `SuppFig5_SourceData.xlsx`

**a**, D4; **b**, D5; **c**, D6; **d**, D7. Squares, males; circles, females; lighter lines, earlier waves. GBD MDD (both sexes, 2021–2023) is shown in **a**, **b** and **d** for scale. Linear y axis.

## Supplementary Fig. 6 | Trend sensitivity to the item set: full CES-D-10, the eight negatively worded items, and the six non-somatic items.
*File:* `SuppFig6_trend_sensitivity_item_sets.pdf` · *Source data:* `SuppFig6_SourceData.xlsx`

**a**, Both sexes; **b**, males; **c**, females. Age-standardized prevalence indexed to 2011 = 100 with 95% CIs, for CES-D-10 ≥10 (all ten items), the eight negatively worded items ≥8 (the two reversed items, "hopeful about the future" and "was happy", excluded; proportional threshold 8/24) and the six non-somatic items ≥6. The two reversed items behaved anomalously in 2013 (scores 0.3–0.4 points higher than in other waves) and in 2020 (near-zero correlation with "felt depressed"). Grey band, fieldwork of the 2021–2023 wave.

**Note.** The 2011→2013 fall was {100*RES['tr_D1_2011_2013'][2]:+.1f}% (95% CI {100*RES['tr_D1_2011_2013'][3]:+.1f} to {100*RES['tr_D1_2011_2013'][4]:+.1f}) with all ten items and {100*RES['tr_D8neg_2011_2013'][2]:+.1f}% ({100*RES['tr_D8neg_2011_2013'][3]:+.1f} to {100*RES['tr_D8neg_2011_2013'][4]:+.1f}) with the eight negative items; the 2011→2021–2023 change was {100*RES['tr_D1_2011_2021–2023'][2]:+.1f}% (CI {100*RES['tr_D1_2011_2021–2023'][3]:+.1f} to {100*RES['tr_D1_2011_2021–2023'][4]:+.1f}) versus {100*RES['tr_D8neg_2011_2021–2023'][2]:+.1f}% ({100*RES['tr_D8neg_2011_2021–2023'][3]:+.1f} to {100*RES['tr_D8neg_2011_2021–2023'][4]:+.1f}); the pooled ≥75 vs 50–59 y prevalence ratio was {RES['grad_D1'][0]:.2f} ({RES['grad_D1'][1]:.2f}–{RES['grad_D1'][2]:.2f}) versus {RES['grad_D8neg'][0]:.2f} ({RES['grad_D8neg'][1]:.2f}–{RES['grad_D8neg'][2]:.2f}). Source data: `SuppFig6_SourceData.xlsx` (sheets a–c).

## Supplementary Fig. 7 | Projected change 2023→2035 in the number of people meeting each definition, by age band, under GBD constant rates, CHARLS D1 constant rates, CHARLS D1 trend and CHARLS D3 constant rates.
*File:* `SuppFig7_projected_change_by_age_band.pdf` · *Source data:* `SuppFig7_SourceData.xlsx`

**a**, Bars give the percentage change in persons aged 50–59, 60–74 and ≥75 years between the 2023 count (GBD 2023 population) and the 2035 count (WPP 2024 medium variant); error bars are 95% intervals (CHARLS: PSU bootstrap of the rates, with the trend refitted in each replicate; GBD: UI draws; populations fixed).
"""
(V1 / "03_图注_Figure_Legends.md").write_text(LEG, encoding="utf-8")

# ============================================================================= 12. Results summary (Chinese, numbers from this run)
def mi(x):
    return f"{x / 1e4:,.0f} 万"


def mici(key):
    """'14,854 万（14,290–15,418）' from RES[n…_key] and RES[n…ci_key]."""
    stem, code = key.split("_", 1)
    v, (lo, hi) = RES[f"{stem}_{code}"], RES[f"{stem}ci_{code}"]
    return f"{mi(v)}（{lo / 1e4:,.0f}–{hi / 1e4:,.0f}）"


def trci(key):
    t = RES[key]
    return f"{100*t[2]:+.1f}%（{100*t[3]:+.1f} 至 {100*t[4]:+.1f}）"


SUM = f"""# 结果摘要（MS1 V1，自动生成）

> 数据：{DATA_VERSION}。所有数字由 `09_代码与质控_Code_QC/01_run_analysis.py` 生成。括号内一律为 95% 区间。
> **CHARLS 区间**：单格患病率、ASR（含敏感性分析 ASR）、患病率比及其变化用 Taylor 线性化（社区为 PSU；ASR 对整个标化和线性化，保留同社区各年龄格之间的协方差——若把年龄格当作独立，SE 会低估约 {100*(1-1/RES['asr_indep_ratio'][0]):.0f}–{100*(1-1/RES['asr_indep_ratio'][1]):.0f}%）；**跨轮合并的估计**（患病率比、女/男比、OR）对各轮做联合线性化，计入各轮共享社区和重复受访者造成的相关（合并 PR 的 SE 比按独立轮次计算大约 {100*RES['pool_se_ratio'][0]:.0f}–{100*RES['pool_se_ratio'][1]:.0f}%）；人数、预测、三因素分解和倾向点曲线用**设计自助法**（每轮以社区为单位有放回重抽 {NBOOT:,} 次，Rao–Wu 校正，每次重算全部年龄–性别格患病率及所有派生量，取 2.5–97.5 百分位）。**GBD 区间**：各年龄–性别格 UI 的对数正态 Monte Carlo（{NDRAW:,} 次，假设年龄组间独立）。两源都参与的量（比值、差值、GBD/CHARLS 比）把自助法重抽与 GBD 抽样逐一配对，视两源独立；人口固定不计不确定性。D1 ASR 的自助法 SE 为线性化 Taylor SE 的 {RES['asr_boot_ratio'][0]:.2f}–{RES['asr_boot_ratio'][1]:.2f} 倍，两法一致（`qc/asr_se_taylor_vs_bootstrap.csv`）。
> 标准人口：GBD 中国 {STD_YEAR} 年 50 岁以上（8 个 5 岁组，男女合计）。第六轮 CHARLS 与 GBD 2021–2023 按访谈年份构成加权的混合值比较（{share_txt}）。

## ① 样本（Table 1）

- 六轮 50 岁以上、CES-D-10 十项完整且有权重的受访者：{', '.join(f'{WLAB[w]} 年 {int(SAMPLE[w]):,} 人' for w in WAVES)}，合计 {RES['n_personwaves']:,} 人次。
- D1（CES-D-10 ≥10）年龄标化率 2021–2023 年为 {pct(RES['asr_2026_D1'])}（{pct(asr_row('CHARLS', 'D1', 2026, 3).lo)}–{pct(asr_row('CHARLS', 'D1', 2026, 3).hi)}）；同期 GBD MDD 为 {pct(RES['asr_2026_568'], 2)}（{pct(asr_row('GBD', 568, 2026, 3).lo, 2)}–{pct(asr_row('GBD', 568, 2026, 3).hi, 2)}），GBD 抑郁障碍为 {pct(RES['asr_2026_567'], 2)}（{pct(asr_row('GBD', 567, 2026, 3).lo, 2)}–{pct(asr_row('GBD', 567, 2026, 3).hi, 2)}）。两者口径不同，水平不直接比较（设计 §4、§10）。
- Table 1 的 D1–D7 粗患病率和 CES-D-10 均分均带 95% CI（样本描述性指标仍为点估计）。

## ② 年龄结构（Q1，Fig. 1，Supp Fig. 1、3，Supp Table 5）

- CHARLS D1 的 75 岁以上与 50–59 岁患病率之比（六轮合并）：男女合计 {pr1[0]:.2f}（95% CI {pr1[1]:.2f}–{pr1[2]:.2f}），男性 {prm[0]:.2f}（{prm[1]:.2f}–{prm[2]:.2f}），女性 {prf[0]:.2f}（{prf[1]:.2f}–{prf[2]:.2f}）。D3（≥15）为 {pr3[0]:.2f}（{pr3[1]:.2f}–{pr3[2]:.2f}）。
- 同一比值在 GBD 中：MDD {pr1[3]:.2f}（UI {pr1[5]:.2f}–{pr1[6]:.2f}），抑郁障碍 {pr1[4]:.2f}（{pr1[7]:.2f}–{pr1[8]:.2f}）（各轮匹配年份平均）。
- 只用 6 个非躯体条目（≥6 分）时，比值为 {prns[0]:.2f}（{prns[1]:.2f}–{prns[2]:.2f}），说明梯度不只由躯体条目造成。
- 加权 logistic 回归中 D1 每增加 10 岁的 OR（六轮逆方差合并）：男女合计 {RES['or_D1_pooled'][3][0]:.2f}（{RES['or_D1_pooled'][3][1]:.2f}–{RES['or_D1_pooled'][3][2]:.2f}），男性 {RES['or_D1_pooled'][1][0]:.2f}（{RES['or_D1_pooled'][1][1]:.2f}–{RES['or_D1_pooled'][1][2]:.2f}），女性 {RES['or_D1_pooled'][2][0]:.2f}（{RES['or_D1_pooled'][2][1]:.2f}–{RES['or_D1_pooled'][2][2]:.2f}）；GBD MDD 对应的每 10 岁患病率比为 {RES['gslope_568'][3][0]:.3f}（UI {RES['gslope_568'][3][1]:.3f}–{RES['gslope_568'][3][2]:.3f}）。

## ③ 性别比（Q1，Fig. 2，Supp Table 7）

- CHARLS D1 女/男比（六轮合并）：全部 50 岁以上 {srall[0]:.2f}（{srall[1]:.2f}–{srall[2]:.2f}），50–54 岁 {sr45[0]:.2f}（{sr45[1]:.2f}–{sr45[2]:.2f}），85 岁以上 {sr85[0]:.2f}（{sr85[1]:.2f}–{sr85[2]:.2f}）。
- GBD MDD 女/男比在各年龄组之间只在 {gsr[0]:.2f}–{gsr[1]:.2f} 之间变动。

## ④ 时间趋势（Q3，Fig. 3，Supp Table 9）

- 2011 → 2021–2023 年龄标化率：CHARLS D1 {pct(t1[0])} → {pct(t1[1])}（{100*t1[2]:+.1f}%，CI {100*t1[3]:+.1f} 至 {100*t1[4]:+.1f}）；D3 {pct(t3[0])} → {pct(t3[1])}（{100*t3[2]:+.1f}%，CI {100*t3[3]:+.1f} 至 {100*t3[4]:+.1f}）；D2 {100*RES['trend_D2'][2]:+.1f}%（{100*RES['trend_D2'][3]:+.1f} 至 {100*RES['trend_D2'][4]:+.1f}）；D5 {100*RES['trend_D5'][2]:+.1f}%（{100*RES['trend_D5'][3]:+.1f} 至 {100*RES['trend_D5'][4]:+.1f}）。
- GBD MDD {pct(t568[0], 2)} → {pct(t568[1], 2)}（{100*t568[2]:+.1f}%，UI {100*t568[3]:+.1f} 至 {100*t568[4]:+.1f}）；GBD 抑郁障碍 {pct(t567[0], 2)} → {pct(t567[1], 2)}（{100*t567[2]:+.1f}%，UI {100*t567[3]:+.1f} 至 {100*t567[4]:+.1f}）。
- 2018 → 2020：CHARLS D1 {100*RES['trend1820_D1'][0]:+.1f}%（CI {100*RES['trend1820_D1'][1]:+.1f} 至 {100*RES['trend1820_D1'][2]:+.1f}）；GBD MDD {100*RES['trend1820_568'][0]:+.1f}%（UI {100*RES['trend1820_568'][1]:+.1f} 至 {100*RES['trend1820_568'][2]:+.1f}）。

## ⑤ 人口规模与老龄化（Q2，Fig. 4–5，Table 3，Supp Table 11 and 12）

- 50 岁以上人口：2011 年 {RES['pop45_2011']/1e8:.2f} 亿（GBD），2023 年 {RES['pop45_2023']/1e8:.2f} 亿（GBD），2035 年 {RES['pop45_2035']/1e8:.2f} 亿（WPP 2024 中方案）；60 岁以上占比 {pct(RES['pop60_share_2023'], 0)} → {pct(RES['pop60_share_2035'], 0)}。
- 2023 年人数（CHARLS = 2021–2023 轮年龄–性别别率 × GBD 2023 年人口；Fig. 4 中画在 2021.4 的点用的是混合年份人口，低 4%）：GBD MDD {mici('n2023_568')}，GBD 抑郁障碍 {mici('n2023_567')}；CHARLS D1 {mici('n2023_D1')}，D2 {mici('n2023_D2')}，D3 {mici('n2023_D3')}，D5 {mici('n2023_D5')}，D7（阳性且无诊断）{mici('n2023_D7')}。CHARLS 与 GBD MDD 人数之比：D1 {RES['ratio2023_D1'][0]:.1f}（{RES['ratio2023_D1'][1]:.1f}–{RES['ratio2023_D1'][2]:.1f}），D2 {RES['ratio2023_D2'][0]:.1f}（{RES['ratio2023_D2'][1]:.1f}–{RES['ratio2023_D2'][2]:.1f}），D3 {RES['ratio2023_D3'][0]:.1f}（{RES['ratio2023_D3'][1]:.1f}–{RES['ratio2023_D3'][2]:.1f}），D5 {RES['ratio2023_D5'][0]:.1f}（{RES['ratio2023_D5'][1]:.1f}–{RES['ratio2023_D5'][2]:.1f}）。
- 2011→2023 增量分解（人口规模 / 年龄结构 / 年龄别率）：GBD MDD 总增 {mi(d568[0])}（{mi(d568[7])} 至 {mi(d568[8])}），其中老龄化 {mi(d568[2])}（{mi(d568[9])} 至 {mi(d568[10])}），占 {sh_(d568, 4)}；CHARLS D1 总增 {mi(dD1[0])}（{mi(dD1[7])} 至 {mi(dD1[8])}），老龄化 {mi(dD1[2])}（{mi(dD1[9])} 至 {mi(dD1[10])}），占 {sh_(dD1, 4)}；D3 老龄化占 {sh_(dD3, 4)}。
- 2023→2035（率固定；变化 % 和老龄化占比按 WPP 序列计算，与 Fig. 5b 一致）：GBD MDD {mici('n2023_568')} → {mici('n2035_568')}（{RES['chg2335_568'][0]:+.1f}%，{RES['chg2335_568'][1]:+.1f} 至 {RES['chg2335_568'][2]:+.1f}），老龄化占增量 {sh_(e568, 3)}；CHARLS D1 {mici('n2023_D1')} → {mici('n2035_D1')}（{RES['chg2335_D1'][0]:+.1f}%，{RES['chg2335_D1'][1]:+.1f} 至 {RES['chg2335_D1'][2]:+.1f}），老龄化占 {sh_(eD1, 3)}；D2 老龄化占 {sh_(RES['dec2335_D2'], 3)}；D3 {mici('n2023_D3')} → {mici('n2035_D3')}，老龄化占 {sh_(eD3, 3)}；D5 老龄化占 {sh_(RES['dec2335_D5'], 3)}。
- 趋势延续情景 2035 年（上界）：D1 {mi(RES['tr2035_D1'][0])}（{mi(RES['tr2035_D1'][1])} 至 {mi(RES['tr2035_D1'][2])}），D3 {mi(RES['tr2035_D3'][0])}（{mi(RES['tr2035_D3'][1])} 至 {mi(RES['tr2035_D3'][2])}）。

## ⑥ 水平校准的可行域（Q4，Fig. 6）

- CHARLS 2021–2023 D1 粗患病率 {pct(tipD1[0])}（{pct(tipD1[5])}–{pct(tipD1[6])}），GBD MDD 粗患病率 {pct(tipD1[1], 2)}（UI {pct(tipD1[7], 2)}–{pct(tipD1[8], 2)}）。若 D1 的敏感度为 0.90，要使 Rogan–Gladen 校正后的患病率等于 GBD MDD，特异度须为 {tipD1[2]:.3f}（{tipD1[3]:.3f}–{tipD1[4]:.3f}）；D2 须为 {tipD2[2]:.3f}（{tipD2[3]:.3f}–{tipD2[4]:.3f}），D3 须为 {tipD3[2]:.3f}（{tipD3[3]:.3f}–{tipD3[4]:.3f}）。区间来自 CHARLS 自助法重抽与 GBD 抽样的配对。
- 没有大陆社区 50 岁以上人群 CES-D-10 对照结构化诊断的研究可供定点，因此本版不下“水平偏差”的结论（设计 §4 结论分级）。

## ⑦ 敏感性（Supp Table 10，Supp Fig. 6）

- **条目集敏感性（8 条负向条目，去掉两条反向计分的“有希望”“愉快”）**：2011→2013 的下降，十项为 {trci('tr_D1_2011_2013')}，8 条负向为 {trci('tr_D8neg_2011_2013')}；2013→2015 分别为 {trci('tr_D1_2013_2015')} 与 {trci('tr_D8neg_2013_2015')}；2011→2021–2023 分别为 {trci('tr_D1_2011_2021–2023')} 与 {trci('tr_D8neg_2011_2021–2023')}；2018→2020 分别为 {trci('tr_D1_2018_2020')} 与 {trci('tr_D8neg_2018_2020')}。
- 年龄梯度（≥75 vs 50–59，六轮合并）：十项 {RES['grad_D1'][0]:.2f}（{RES['grad_D1'][1]:.2f}–{RES['grad_D1'][2]:.2f}），8 条负向 {RES['grad_D8neg'][0]:.2f}（{RES['grad_D8neg'][1]:.2f}–{RES['grad_D8neg'][2]:.2f}），6 条非躯体 {RES['grad_D6ns'][0]:.2f}（{RES['grad_D6ns'][1]:.2f}–{RES['grad_D6ns'][2]:.2f}）。
- D1 年龄标化率（%）在各种选择下的取值，括号为 95% CI（Taylor 线性化，与 Table 2 同法；n/a = 该轮无此信息）：

{SENS.to_markdown(index=False)}

## ⑧ 质控

- 共 {len(QC_ROWS)} 项检查，见 `09_代码与质控_Code_QC/qc/qc_checks.csv`。
"""
(V1 / "08_结果摘要_Results_summary.md").write_text(SUM, encoding="utf-8")

# ============================================================================= 13. QC output
qc_df = pd.DataFrame(QC_ROWS)
qc_df.to_csv(QC / "qc_checks.csv", index=False, encoding="utf-8-sig")
EST.to_csv(QC / "charls_estimates_long.csv", index=False)
GBA.to_csv(QC / "gbd_aggregated_50plus.csv", index=False)
n_fail = int((~qc_df["pass"]).sum())
print(f"QC: {len(qc_df)} checks, {n_fail} failed")
if n_fail:
    print(qc_df[~qc_df["pass"]].to_string())
print("Figures:", sorted(p.name for p in FIG.glob("*.png")))
print("Supp figures:", sorted(p.name for p in FIG_S.glob("*.png")))
print("Done.")
