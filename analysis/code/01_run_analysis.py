#!/usr/bin/env python3
"""Compare depression measures in GBD 2023 and CHARLS among adults aged 50 or older.

Inputs: the processed CHARLS panel, GBD 2023 estimates for China and
UN WPP 2024 population projections under data/.
Outputs: figures, tables, source data and numerical method diagnostics
under the configured output directory.

Figures use Helvetica, lettered panels, PDF and 300 dpi PNG exports.
Source-data workbooks contain one worksheet per panel."""

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import NullFormatter
from matplotlib.patches import FancyBboxPatch, Patch

from settings import OUTPUT_DIR, PANEL, DATA_DIR, require_files, validate_panel, CROSSWALK

require_files([PANEL, CROSSWALK, DATA_DIR / "GBD2023" / "China_mental_disorders_GBD2023_1990_2023.csv",
               DATA_DIR / "WPP2024" / "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz"])
ANALYSIS_DIR = OUTPUT_DIR
GBD_CSV = DATA_DIR / "GBD2023" / "China_mental_disorders_GBD2023_1990_2023.csv"
WPP_CSV = DATA_DIR / "WPP2024" / "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz"
FIG, FIG_S = ANALYSIS_DIR / "02_Figures", ANALYSIS_DIR / "05_Supplementary_Figures"
TAB_MAIN, TAB_S = ANALYSIS_DIR / "04_Tables", ANALYSIS_DIR / "06_Supplementary_Tables"
SD, DIAGNOSTICS = ANALYSIS_DIR / "07_SourceData", ANALYSIS_DIR / "diagnostics"
for d in (FIG, FIG_S, TAB_MAIN, TAB_S, SD, DIAGNOSTICS):
    d.mkdir(parents=True, exist_ok=True)


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
DEFS = {
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
METHOD_CHECKS, SOURCE = [], {}


def method_check(check, detail, diff, tol):
    """Record numerical identities and estimator comparisons."""
    passed = bool(np.isfinite(diff) and abs(diff) <= tol)
    METHOD_CHECKS.append({"check": check, "detail": detail,
                          "difference": float(diff), "tolerance": float(tol), "pass": passed})
    if not passed:
        raise ValueError(f"Numerical method check failed: {check}; {detail}; difference={diff}, tolerance={tol}")


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
    if s.startswith("-") and float(s.replace(",", "")) == 0:
        s = s[1:]
    return s.replace("-", "−")


def fmt_ci(p, lo, hi, k=1):
    return "—" if pd.isna(p) else f"{fmt(p, k)} ({fmt(lo, k)} to {fmt(hi, k)})"


def panel_letter(ax, letter, x=-0.12, y=1.04):
    ax.text(x, y, letter, transform=ax.transAxes, fontsize=11, fontweight="bold", va="bottom", ha="left")


def age_group(a):
    return pd.cut(a, bins=AGE_LO + [200], right=False, labels=AGES)


P = pd.read_csv(PANEL, low_memory=False)
validate_panel(P)
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
A["d1_dxk"] = A["d1"].where(A.dx_emot_ever.notna())
A["d6ns"] = (A.cesd6_nonsomatic >= 6).astype(float).where(A.cesd6_nonsomatic.notna())
A["d8neg"] = (A.cesd8_negative >= 8).astype(float).where(A.cesd8_negative.notna())
for t in (8, 12, 15, 16):
    A[f"thr{t}"] = (A.cesd10 >= t).astype(float)
A["d1_pror"] = (A.cesd10_prorated >= 10).astype(float).where(A.cesd10_prorated.notna())


AP = P[(P.age >= 50) & P.sex.isin([1, 2]) & P.weight.notna() & P.cesd10_prorated.notna() & (P.crosssection == 1)].copy()
AP["agegrp"] = age_group(AP.age)
AP["d1_pror"] = (AP.cesd10_prorated >= 10).astype(float)
method_check("Prorated sample contains every complete-case respondent", "rows of A not in AP", float(len(A.index.difference(AP.index))), 0)
A["female"] = (A.sex == 2).astype(float)
A["age60"] = (A.age >= 60).astype(float)
A["age75"] = (A.age >= 75).astype(float)
N_PSU = A.groupby("wave")["communityID"].nunique()
SAMPLE = A.groupby("wave").size()


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


G = pd.read_csv(GBD_CSV, low_memory=False)
required_gbd = {"location_id", "measure_id", "cause_id", "sex_id", "age_id", "year", "metric_id", "val", "lower", "upper"}
missing = required_gbd.difference(G.columns)
if missing:
    raise ValueError(f"Missing GBD columns: {sorted(missing)}")
if not G.location_id.eq(6).all():
    raise ValueError("GBD input must contain only China (location_id 6).")
if G.duplicated(["location_id", "measure_id", "cause_id", "sex_id", "age_id", "year", "metric_id"]).any():
    raise ValueError("Duplicate GBD estimate keys.")
if not np.isfinite(G[["val", "lower", "upper"]].to_numpy()).all():
    raise ValueError("GBD estimates and uncertainty bounds must be finite.")
if ((G.lower < 0) | (G.lower > G.val) | (G.val > G.upper)).any():
    raise ValueError("Invalid GBD uncertainty bounds.")
G = G[(G.measure_id == 5) & G.cause_id.isin([558, 567, 568, 571]) & G.age_id.isin(GBD_AGE) & (G.year >= 2011)]
num = G[G.metric_id == 1].rename(columns={"val": "n", "lower": "n_lo", "upper": "n_hi"})
rate = G[G.metric_id == 3].rename(columns={"val": "r", "lower": "r_lo", "upper": "r_hi"})
key = ["cause_id", "sex_id", "age_id", "year"]
GB = num[key + ["n", "n_lo", "n_hi"]].merge(rate[key + ["r", "r_lo", "r_hi"]], on=key, validate="one_to_one", how="outer", indicator=True)
if not GB["_merge"].eq("both").all():
    raise ValueError("GBD number and rate keys do not match.")
if (GB.r <= 0).any():
    raise ValueError("GBD rates must be positive to recover population denominators.")
GB = GB.drop(columns="_merge")
GB["pop"] = GB.n / GB.r * 1e5
GB["agegrp"] = GB.age_id.map(GBD_AGE)

pp = GB.pivot_table(index=["sex_id", "age_id", "year"], columns="cause_id", values="pop")
method_check("GBD population identical across causes (Number/Rate)", "max relative difference 567 vs 568, all cells",
   float(((pp[567] - pp[568]).abs() / pp[568]).max()), 1e-3)

def lognorm_draws(val, lo, hi):
    val, lo, hi = np.asarray(val, float), np.asarray(lo, float), np.asarray(hi, float)
    sig = np.where((hi > lo) & (lo > 0), (np.log(hi) - np.log(np.maximum(lo, 1e-12))) / (2 * 1.96), 0.0)
    return np.exp(np.log(np.maximum(val, 1e-12))[None, :] + sig[None, :] * RNG.standard_normal((NDRAW, len(val))))

GB = GB.reset_index(drop=True)
DR_N = lognorm_draws(GB.n, GB.n_lo, GB.n_hi)
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
GBA_D = np.column_stack([GBA_draws[i] for i in GBA.index])
GBA = GBA.reset_index(drop=True)
GBA["prev_lo"] = np.percentile(GBA_D, 2.5, axis=0)
GBA["prev_hi"] = np.percentile(GBA_D, 97.5, axis=0)
GIDX = {k: i for i, k in enumerate(zip(GBA.cause_id, GBA.sex_id, GBA.year, GBA.agegrp.astype(str)))}

both = GBA[GBA.sex_id == 3].set_index(["cause_id", "year", "agegrp"]).n
mf = GBA[GBA.sex_id.isin([1, 2])].groupby(["cause_id", "year", "agegrp"], observed=True).n.sum()
method_check("GBD both sexes = males + females (numbers)", "max relative difference, all cause/year/age cells",
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


STD = gbd_pop(3, STD_YEAR)
STD_W = STD / STD.sum()


W = pd.read_csv(WPP_CSV, low_memory=False)
required_wpp = {"Location", "Variant", "Time", "AgeGrpStart", "PopMale", "PopFemale", "PopTotal"}
missing = required_wpp.difference(W.columns)
if missing:
    raise ValueError(f"Missing WPP columns: {sorted(missing)}")
W = W[(W.Location == "China") & (W.Variant == "Medium") & W.Time.between(2011, 2035)].copy()
W = W[W.AgeGrpStart >= 50]
if W.duplicated(["Time", "AgeGrpStart"]).any():
    raise ValueError("Duplicate WPP year-age keys for China, medium variant.")
if set(W.Time.unique()) != set(range(2011, 2036)):
    raise ValueError("WPP input must cover every year from 2011 to 2035.")
values = W[["PopMale", "PopFemale", "PopTotal"]].to_numpy()
if not np.isfinite(values).all() or (values < 0).any():
    raise ValueError("WPP populations must be finite and nonnegative.")
W["agegrp"] = pd.cut(W.AgeGrpStart, bins=AGE_LO + [200], right=False, labels=AGES)
WPP = (W.groupby(["Time", "agegrp"], observed=True)[["PopMale", "PopFemale", "PopTotal"]].sum() * 1000).reset_index()
WPP = WPP.rename(columns={"Time": "year"})
if len(WPP) != 25 * len(AGES) or (WPP.PopTotal <= 0).any():
    raise ValueError("WPP input must contain all eight analysis age groups in every year.")
WPP["agegrp"] = pd.Categorical(WPP.agegrp, AGES, ordered=True)


def wpp_pop(sex, year):
    col = {1: "PopMale", 2: "PopFemale", 3: "PopTotal"}[sex]
    return WPP[WPP.year == year].sort_values("agegrp")[col].values


for s in (1, 2, 3):
    method_check("WPP 2024 vs GBD population aged ≥50, 2023", f"{SEXES[s]}: relative difference (informational, <10%)",
       float(wpp_pop(s, 2023).sum() / gbd_pop(s, 2023).sum() - 1), 0.10)


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


for w in WAVES:
    for s in (1, 2, 3):
        for code in ("D2", "D3", "D5", "D7"):
            p1, _, _, _ = est_vec(w, s, "D1dx" if code == "D7" else "D1")
            pk, _, _, _ = est_vec(w, s, code)
            m = ~np.isnan(pk) & ~np.isnan(p1)
            method_check(f"Case definitions nested: {code} ≤ D1", f"{WLAB[w]}, {SEXES[s]}, max excess over D1 (0 = none)",
               max(0.0, float(np.nanmax(np.where(m, pk - p1, -1)))), 1e-9)


NBOOT = NDRAW
BOOT_COLS = dict(EST_COLS)
BOOT_COLS.pop("C"), BOOT_COLS.pop("C8"), BOOT_COLS.pop("D1dx"), BOOT_COLS.pop("D1pror")
BOOT = {}
BOOT_MULT = {}
for w in WAVES:
    dw = A[A.wave == w]
    cidx, comms = pd.factorize(dw.communityID)
    nc = len(comms)
    M = RNG.multinomial(nc - 1, np.full(nc, 1.0 / nc), size=NBOOT).astype(float)
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
            num, den = M @ S.T, M @ T.T
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


_bias = max(abs(float(np.nanmean(BOOT[(w, 3, a, "D1")]) - est(w, 3, a, "D1").p)) for w in WAVES for a in AGES)
method_check("Bootstrap replicate mean equals point estimate", "D1, both sexes, all waves × age groups, max |mean − p| (ratio-estimator bias in small cells)", _bias, 0.01)


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
    if np.isnan(p).any():
        return np.nan, np.nan
    if d is None:
        src = AP if code == "D1pror" else A
        d = src[src.wave == w] if s == 3 else src[(src.wave == w) & (src.sex == s)]
    asr, se_t = taylor_lincomb(d, EST_COLS[code], d.agegrp.astype(str).values, dict(zip(AGES, STD_W)), N_PSU[w], wcol)
    return asr, se_t


def asr_charls_indep(w, s, code):
    """Independent-cell variance estimator for comparison with covariance-aware estimates."""
    p, se, _, _ = est_vec(w, s, code)
    return float((STD_W * p).sum()), float(np.sqrt((STD_W ** 2 * se ** 2).sum()))


_a1, _ = asr_charls(2011, 3, "D1")
method_check("Linearised ASR point estimate equals Σ STD_W·p", "D1, both sexes, 2011", float(_a1 - asr_charls_indep(2011, 3, "D1")[0]), 1e-12)


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
    for s in (1, 2, 3):
        a, lo, hi, _ = asr_gbd(cause, s, 2026)
        pw = gbd_pop(s, 2026)
        pm, _ = gbd(cause, s, 2026)
        ASR.append({"source": "GBD", "def": cause, "wave": 2026, "year": W6_YEAR, "sex_id": s, "asr": a, "se": np.nan, "lo": lo, "hi": hi,
                    "crude": float((pm * pw).sum() / pw.sum()), "crude_lo": np.nan, "crude_hi": np.nan, "n": np.nan})
ASR = pd.DataFrame(ASR)

p20, _ = gbd(568, 3, 2020)
method_check("ASR with own-population standard equals crude prevalence", "GBD MDD, both sexes, 2020",
   float((STD_W * p20).sum() - gbd_n(568, 3, 2020).sum() / STD.sum()), 1e-9)


def asr_row(source, code, w, s):
    r = ASR[(ASR.source == source) & (ASR["def"] == code) & (ASR.wave == w) & (ASR.sex_id == s)]
    return r.iloc[0]


ASR_BOOT_CMP = []
for w in WAVES:
    r = asr_row("CHARLS", "D1", w, 3)
    se_b = float(np.nanstd((boot_vec(w, 3, "D1") * STD_W[None, :]).sum(axis=1), ddof=1))
    se_i = asr_charls_indep(w, 3, "D1")[1]
    ASR_BOOT_CMP.append({"wave": WLAB[w], "asr": r.asr, "se_taylor_linearised": r.se, "se_bootstrap": se_b, "se_taylor_independent_cells": se_i,
                         "ratio_bootstrap_to_linearised": se_b / r.se, "ratio_linearised_to_independent": r.se / se_i})
    method_check("Bootstrap SE of ASR vs linearised Taylor SE", f"D1, both sexes, {WLAB[w]}: ratio − 1", se_b / r.se - 1, 0.10)
ASR_BOOT_CMP = pd.DataFrame(ASR_BOOT_CMP)


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
GRAD_GBD_DRAWS = {}
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


def pool(df, col, secol):
    wts = 1 / df[secol] ** 2
    m = (df[col] * wts).sum() / wts.sum()
    return m, np.sqrt(1 / wts.sum())


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
        for cause in (568, 567):
            gd = np.mean([GRAD_GBD_DRAWS[(w, s, cause)] for w in sub.wave], axis=0)
            row[f"gbd{cause}_pr_lo"], row[f"gbd{cause}_pr_hi"] = pci(gd)
        POOLED_GRAD.append(row)
POOLED_GRAD = pd.DataFrame(POOLED_GRAD)
_sr = (POOLED_GRAD.se_joint / POOLED_GRAD.se_independent - 1)
_p, _z = z_prev(A[A.wave == 2011], "d1")
method_check("Joint linearisation reproduces the single-wave Taylor SE", "D1 2011 both sexes ≥50: relative difference (450 vs 449 PSUs)",
   float(joint_se([1.0], [_z]) / est(2011, 3, "All ≥50", "D1").se - 1), 0.01)
for _, _r in POOLED_GRAD[(POOLED_GRAD.sex_id == 3) & POOLED_GRAD["def"].isin(["D1", "D3"])].iterrows():
    method_check("Pooled PR: joint-linearised SE / independent-wave SE (informational)", f"{_r['def']}, both sexes", float(_r.se_joint / _r.se_independent - 1), 0.50)


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
    if return_if:
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
method_check("Vectorised WLS slope equals polyfit", "GBD MDD 2020 both sexes, point estimate",
   float(wls_slope(np.array(AGE_MID), np.log(gbd(568, 3, 2020)[0]), gbd_pop(3, 2020)) - np.polyfit(np.array(AGE_MID), np.log(gbd(568, 3, 2020)[0]), 1, w=np.sqrt(gbd_pop(3, 2020)))[0]), 1e-9)


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


TREND = []
for code in MAIN_DEFS + ["D8neg", "D6ns"]:
    for s in (1, 2, 3):
        for w0, w1 in [(2011, 2026), (2018, 2020), (2020, 2026), (2011, 2018), (2011, 2013), (2013, 2015)]:
            r0, r1 = asr_row("CHARLS", code, w0, s), asr_row("CHARLS", code, w1, s)
            TREND.append({"source": "CHARLS", "def": code, "sex_id": s, "from": WLAB[w0], "to": WLAB[w1], "asr_from": r0.asr, "asr_to": r1.asr,
                          "abs_change": r1.asr - r0.asr, "rel_change": r1.asr / r0.asr - 1,
                          "rel_lo": np.nan, "rel_hi": np.nan})

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


def counts_from_rates(rates_by_sex, pops_by_sex):
    """rates_by_sex/pops_by_sex: {1: vec(9), 2: vec(9)} -> total persons."""
    return float(sum((rates_by_sex[s] * pops_by_sex[s]).sum() for s in (1, 2)))


CNT_DRAWS = {}
SLICES = {"n45": slice(0, 8), "n60": slice(2, 8), "n75": slice(5, 8)}


def count_draws(rate_draws, pops):
    """rate_draws: {1: (NDRAW, 8), 2: (NDRAW, 8)}; pops: {1: (8,), 2: (8,)} -> {col: (NDRAW,)} for ≥50, ≥60, ≥75."""
    return {col: sum((rate_draws[s][:, sl] * pops[s][None, sl]).sum(axis=1) for s in (1, 2)) for col, sl in SLICES.items()}


def gbd_rate_draws(cause, year):
    return {s: gbd(cause, s, year)[1] for s in (1, 2)}


CNT = []
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

_d = A[A.wave == 2026]
_cells = _d.sex.astype(int).astype(str) + "|" + _d.agegrp.astype(str)
_coef = {f"{s}|{a}": gbd_pop(s, 2026)[j] for s in (1, 2) for j, a in enumerate(AGES)}
_n_t, _se_t = taylor_lincomb(_d, "d1", _cells.values, _coef, N_PSU[2026])
method_check("Linearised count equals Σ rate × population", "D1, 2021–2023, persons ≥50", float(_n_t - CNT[(CNT.source == "CHARLS") & (CNT["def"] == "D1") & (CNT.wave == 2026)].n45.iloc[0]), 1e-3)
method_check("Bootstrap SE of count vs linearised Taylor SE", "D1, 2021–2023, persons ≥50: ratio − 1",
   float(np.std(CNT_DRAWS[("CHARLS", "D1", 2026, "observed", "n45")], ddof=1) / _se_t - 1), 0.10)


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
            fits[(s, j)] = (keep, np.linalg.solve(X.T @ Wm @ X, X.T @ Wm))
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
                coef = np.log(Pb / (1 - Pb)) @ Amat.T
                cols.append(1 / (1 + np.exp(-(coef[:, 0] + coef[:, 1] * year))))
            else:
                y = np.array([np.log(est(w, s, a, code).p / (1 - est(w, s, a, code).p)) for w in keep])
                coef = Amat @ y
                cols.append(1 / (1 + np.exp(-(coef[0] + coef[1] * year))))
        out[s] = np.column_stack(cols) if draws else np.array(cols)
    return out


_k, _A = TREND_FIT["D1"][(1, 0)]
_ys = np.array([np.log(est(w, 1, "50–54", "D1").p / (1 - est(w, 1, "50–54", "D1").p)) for w in _k])
_ws = np.array([(est(w, 1, "50–54", "D1").p * (1 - est(w, 1, "50–54", "D1").p) / est(w, 1, "50–54", "D1").se) ** 2 for w in _k])
method_check("Trend WLS operator equals np.polyfit", "D1 males 50–54, slope", float((_A @ _ys)[1] - np.polyfit([WAVE_X[w] for w in _k], _ys, 1, w=np.sqrt(_ws))[0]), 1e-9)

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

chk = PROJ[(PROJ.source == "GBD") & (PROJ["def"] == 568) & (PROJ.year == 2035)].n45.iloc[0]
re_ = sum((gbd(568, s, 2023)[0] * wpp_pop(s, 2035)).sum() for s in (1, 2))
method_check("Projection = Σ rate × WPP population", "GBD MDD constant rates, 2035", float(chk - re_), 1e-6)
_r = PROJ[(PROJ.source == "CHARLS") & (PROJ["def"] == "D1") & (PROJ.year == 2035) & (PROJ.scenario == "constant 2021–2023 rates")].iloc[0]
method_check("Projection point estimate lies inside its bootstrap CI", "CHARLS D1 constant rates 2035, persons ≥50 (0 = inside)",
   max(0.0, _r.lo - _r.n45, _r.n45 - _r.hi), 1e-9)


def cnt_draws(source, code, year, scenario="observed", col="n45"):
    if source == "CHARLS" and year == 2023:
        return CNT_DRAWS[("CHARLS", code, 2023, SCEN23, col)]
    return CNT_DRAWS[(source, code, year, scenario, col)]


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
    method_check("Decomposition draws: components sum to total", f"{label}, {source} {code}, max |residual| over draws",
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
method_check("Decomposition components sum to total change", "max absolute residual over all rows",
   float((DEC[["size", "structure", "rate"]].sum(axis=1) - DEC.total).abs().max()), 1e-3)
for code in MAIN_DEFS:
    _e = DEC[(DEC.period.str.startswith("2011")) & (DEC.source == "CHARLS") & (DEC["def"] == code)].iloc[0]
    method_check("2023 planning base equals decomposition end count (2021–2023 rates × GBD 2023 population)", f"CHARLS {code}, persons",
       float(CNT23[CNT23["def"] == code].n45.iloc[0] - _e.n_end), 1e-3)
_r = DEC[(DEC.period.str.startswith("2023")) & (DEC.source == "CHARLS") & (DEC["def"] == "D1")].iloc[0]
method_check("Ageing share point estimate lies inside its bootstrap CI", "2023→2035 CHARLS D1 (0 = inside)",
   max(0.0, _r.share_structure_lo - _r.share_structure, _r.share_structure - _r.share_structure_hi), 1e-9)


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
        spd = (1 - pb[:, None] - pgd[:, None] + pgd[:, None] * SE_GRID[None, :]) / (1 - pgd[:, None])
        sp_lo, sp_hi = pci(spd)
        for se_, sp_, l_, h_ in zip(SE_GRID, sp, sp_lo, sp_hi):
            TIP.append({"def": code, "cause_id": cause, "p_charls": p, "p_charls_lo": r.lo, "p_charls_hi": r.hi,
                        "pi_gbd": pg, "pi_gbd_lo": pg_lo, "pi_gbd_hi": pg_hi, "Se": se_, "Sp_required": sp_, "Sp_required_lo": l_, "Sp_required_hi": h_})
TIP = pd.DataFrame(TIP)
_t = TIP[(TIP["def"] == "D1") & (TIP.cause_id == 568) & np.isclose(TIP.Se, 0.9)].iloc[0]
method_check("Tipping-point Sp point estimate lies inside its CI", "D1 vs GBD MDD at Se = 0.90 (0 = inside)",
   max(0.0, _t.Sp_required_lo - _t.Sp_required, _t.Sp_required - _t.Sp_required_hi), 1e-9)


REF_POINTS = [
    {"def": "D2", "study": "Cheng & Chan 2005", "doi": "10.1002/gps.1314", "population": "Hong Kong, aged ≥60 y referred for psychiatric assessment (n = 398)",
     "reference": "psychiatrist diagnosis, spectrum of depressive disorders", "cutoff": 12, "Se": 0.76, "Sp": 0.55},
]
REF_TAB = pd.DataFrame(REF_POINTS)
for _r in REF_POINTS:
    _p = float(TIP.loc[TIP["def"] == _r["def"], "p_charls"].iloc[0])
    _r["pi_corrected"] = (_p + _r["Sp"] - 1) / (_r["Se"] + _r["Sp"] - 1)
REF_TAB = pd.DataFrame(REF_POINTS)


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

T1.to_csv(TAB_MAIN / "Table1_CHARLS_sample_2011_2023.csv", index=False, encoding="utf-8-sig")


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
T3_NUM = []
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
T3.to_csv(TAB_MAIN / "Table3_planning_base_2023_2035.csv", index=False, encoding="utf-8-sig")

titles = pd.DataFrame([
    {"file": "Table1_CHARLS_sample_2011_2023", "title": "Table 1 | Characteristics of CHARLS respondents aged 50 years or older with complete CES-D-10, by survey wave, 2011–2023",
     "note": "Weighted with cross-sectional individual weights adjusted for household and individual non-response; n and PSUs are unweighted. The mean CES-D-10 score and the prevalence of each case definition are given with 95% confidence intervals (Taylor linearization with communities as primary sampling units; logit-scale intervals for proportions); the other characteristics are point estimates describing the sample. ADL, activities of daily living (dressing, bathing, eating, transferring, toileting); in 2011–2018 the functional-limitation module was skipped for about 30% of respondents, who were younger and healthier, and these are coded as having no limitation. D4 requires participation in the previous wave and is therefore not defined in 2011. D6 is a lifetime self-report of a doctor's diagnosis of emotional, nervous or psychiatric problems. Proxy status is not recorded in 2013 and 2018 (n/a). The 2021–2023 wave was fielded over three years; each respondent is counted once in their response year."},
    {"file": "Table2_ASR_by_definition_and_wave", "title": "Table 2 | Age-standardized prevalence (%) of depression among adults aged 50 years or older in China by case definition and survey wave: CHARLS 2011–2023 and matched GBD 2023 estimates",
     "note": f"All rates are standardized to the same population (GBD China {STD_YEAR}, both sexes, eight 5-year groups from 50–54 to 85+). CHARLS: survey-weighted prevalence with 95% confidence intervals (Taylor linearization of the standardized sum with communities as PSUs, which retains the covariance between age groups sampled from the same communities). GBD: prevalence from IHME GBD 2023 with 95% uncertainty intervals approximated by Monte Carlo sampling of age-specific UIs assuming independence between age groups. For the 2021–2023 wave the GBD comparator is the mixture of GBD 2021, 2022 and 2023 weighted by the CHARLS interview-year distribution ({', '.join(f'{int(y)}: {100*s:.0f}%' for y, s in W6_SHARE.items())}). CES-D-10 is a symptom scale and not a diagnostic instrument; levels are not directly comparable with GBD and are shown to document the range across definitions."},
    {"file": "Table3_planning_base_2023_2035", "title": "Table 3 | Numbers of adults aged 50 years or older in China meeting each depression definition in 2023 and projected to 2035 under the GBD 2023 and CHARLS age- and sex-specific rates",
     "note": f"Values are estimates with 95% intervals in parentheses. 2023 counts apply the age- and sex-specific prevalence to the GBD 2023 population (CHARLS rates are those of the 2021–2023 wave; GBD counts are the published 2023 numbers). 2035 counts apply the same rates to the UN World Population Prospects 2024 medium-variant population; they are demographic scenarios, not forecasts of risk. Because the WPP 2023 population aged ≥50 is 3% smaller than the GBD 2023 population, the change 2023–2035 and the share from ageing are both computed on the WPP series (rates × WPP 2023 → rates × WPP 2035, as in the decomposition of Fig. 5b and Supplementary Table 11) rather than from the two count columns. Intervals for CHARLS-based cells come from a design-based bootstrap of the survey ({NBOOT:,} replicates resampling communities, the primary sampling units, with replacement within each wave and recomputing every age–sex-specific prevalence and all derived quantities); intervals for GBD-based cells propagate the published 95% uncertainty intervals of each age–sex cell by lognormal Monte Carlo draws ({NDRAW:,}); ratios and gaps combine the two sets of draws, treating the sources as independent. Populations are held fixed. Share of increase from ageing is the age–sex-structure term of a three-factor decomposition (population size, age–sex structure, rates) divided by the total change (n/a when the total change is below 10% of the baseline); with constant rates the rate term is zero. Trend continued extrapolates the 2011–2023 cell-level logit trends of CHARLS prevalence to 2035 (each bootstrap replicate refits the trend) and is shown only as a bound. ref., reference category. None of these numbers is a count of clinically diagnosed patients; they are planning bases under different definitions."},
])
titles.to_csv(TAB_MAIN / "table_titles_notes.csv", index=False, encoding="utf-8-sig")


cw = pd.read_csv(CROSSWALK)
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

    d["one"] = 1.0
    p, se, _, _ = wprev(d.assign(weight=1.0), "d1", N_PSU[w])
    lo, hi = ci_logit(p, se)
    row["unweighted crude ≥10"] = fmt_ci(100 * p, 100 * lo, 100 * hi)
    num["unweighted crude ≥10"] = (100 * p, 100 * lo, 100 * hi)
    method_check("Sensitivity: unweighted crude equals simple mean", WLAB[w], float(p - d.d1.mean()), 1e-9)

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
ASR_BOOT_CMP.to_csv(DIAGNOSTICS / "asr_se_taylor_vs_bootstrap.csv", index=False, encoding="utf-8-sig")
ITEM.to_csv(TAB_S / "SuppTable6_item_endorsement_by_age.csv", index=False, encoding="utf-8-sig")

for f in TAB_MAIN.glob("Table*.csv"):
    pd.read_csv(f, encoding="utf-8-sig", dtype=str, keep_default_na=False).to_markdown(open(f.with_suffix(".md"), "w", encoding="utf-8"), index=False, disable_numparse=True)

with pd.ExcelWriter(TAB_S / "All_supplementary_tables_GBD_vs_CHARLS.xlsx") as xw:
    for f in sorted(TAB_S.glob("SuppTable*.csv"), key=lambda f: (int(re.match(r"SuppTable(\d+)", f.stem).group(1)), f.stem)):
        pd.read_csv(f, encoding="utf-8-sig").to_excel(xw, sheet_name=f.stem.split("_")[0], index=False)

r = asr_row("CHARLS", "D1", 2011, 3)


def shade_periods(ax, y0=None):
    ax.axvspan(2010.5, 2023.5, color=PERIOD_COL["observed"], zorder=0, lw=0)
    ax.axvspan(2023.5, 2026.5, color=PERIOD_COL["nowcast"], zorder=0, lw=0)
    ax.axvspan(2026.5, 2035.5, color=PERIOD_COL["projection"], zorder=0, lw=0)


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


def fig3():
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4))
    panels = {}
    specs = [("a", 3, "level"), ("b", 3, "index"), ("c", 1, "index"), ("d", 2, "index")]
    for ax, (letter, s, mode) in zip(axes.flat, specs):
        rows = []
        ax.axvspan(2021, 2023, color="#E6E6E6", lw=0, zorder=0)
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
                if scen.startswith("constant"):
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


def fig6():
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 3.5), sharey=True)
    panels = {}
    for ax, code, letter in zip(axes, ("D1", "D2", "D3"), "abc"):
        sub = TIP[TIP["def"] == code]
        for cause in (568, 567):
            t = sub[sub.cause_id == cause]
            ax.fill_between(t.Se, t.Sp_required_lo, t.Sp_required_hi, color=COL[cause], alpha=0.2, lw=0)
            ax.plot(t.Se, t.Sp_required, LS[cause], color=COL[cause], lw=1.5, label=f"target: {CAUSE_LONG[cause]}")
        ax.fill_between([0.5, 1], [0.0, 0.0], [0.5, 0.0], color="#E6E6E6", lw=0)
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


EST.to_csv(TAB_S / "charls_estimates_long.csv", index=False)
GBA.to_csv(TAB_S / "gbd_aggregated_50plus.csv", index=False)
pd.DataFrame(METHOD_CHECKS).to_csv(DIAGNOSTICS / "numerical_methods.csv", index=False)
print("Figures:", sorted(p.name for p in FIG.glob("*.png")))
print("Supplementary figures:", sorted(p.name for p in FIG_S.glob("*.png")))
print(f"Analysis complete: {ANALYSIS_DIR}")
