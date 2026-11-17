#!/usr/bin/env python3
"""Generate the CHARLS sample flow diagram and data-quality summaries.

Inputs: data/processed/charls_panel_2011_2023.csv and
analysis/code/qc/panel_build_log.csv.
Outputs under output/CHARLS/: PDF and PNG flow diagrams, sample counts,
wave-specific data quality and panel participation tables."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
OUT = REPO_ROOT / "output" / "CHARLS"
OUT.mkdir(exist_ok=True)
PANEL = REPO_ROOT / "data" / "processed" / "charls_panel_2011_2023.csv"
LOG = pd.read_csv(HERE / "qc" / "panel_build_log.csv")

WAVES = [2011, 2013, 2015, 2018, 2020, 2026]
WLAB = {2011: "2011", 2013: "2013", 2015: "2015", 2018: "2018", 2020: "2020", 2026: "2021–2023"}
CESD_VARS = {2011: "dc009–dc018", 2013: "dc009–dc018", 2015: "dc009–dc018", 2018: "dc009–dc018", 2020: "dc016–dc025", 2026: "dc051–dc060"}
plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans"], "font.size": 8, "pdf.fonttype": 42, "savefig.dpi": 300, "savefig.bbox": "tight"})

P = pd.read_csv(PANEL, low_memory=False)


rows = []
for w in WAVES:
    d = P[P.wave == w]
    n0 = len(d)
    asked = d[d.cesd_nmiss < 10]
    comp = asked[asked.cesd_nmiss == 0]
    age50 = comp[comp.age >= 50]
    sexok = age50[age50.sex.isin([1, 2])]
    final = sexok[sexok.weight.notna() & (sexok.crosssection == 1)]
    rows.append({
        "wave": WLAB[w], "wave_code": w,
        "records_stacked": int(LOG[(LOG.wave == w) & (LOG.step == "three file-years stacked")].rows.iloc[0]) if w == 2026 else n0,
        "respondents": n0,
        "cesd_module_answered": len(asked), "excl_cesd_not_asked": n0 - len(asked),
        "cesd_complete": len(comp), "excl_cesd_partial": len(asked) - len(comp),
        "aged_50plus": len(age50), "excl_age_under50_or_missing": len(comp) - len(age50),
        "sex_known": len(sexok), "excl_sex_missing": len(age50) - len(sexok),
        "analytic": len(final), "excl_no_weight_or_not_crosssection": len(sexok) - len(final),
        "age_45_49_with_cesd": int(((comp.age >= 45) & (comp.age < 50)).sum()),
        "psu_analytic": final.communityID.nunique(),
        "d4_defined": int(final.d4_persistent.notna().sum()),
        "weighted_population_50plus_millions": round(final.weight.sum() / 1e6, 1),
    })
FLOW = pd.DataFrame(rows)
FLOW.to_csv(OUT / "07_CHARLS_data_flow_counts.csv", index=False, encoding="utf-8-sig")

A = P[(P.age >= 50) & P.sex.isin([1, 2]) & P.weight.notna() & P.cesd10.notna() & (P.crosssection == 1)]
n_pw, n_persons = len(A), A.ID.nunique()
part = A.groupby("ID").size().value_counts().sort_index()
PART = pd.DataFrame({"waves_in_analytic_sample": part.index, "persons": part.values})
PART["share_pct"] = (100 * PART.persons / PART.persons.sum()).round(1)
pairs = A[A.d4_persistent.notna()].groupby("wave").size().rename("person_waves_with_previous_wave").reset_index()
pairs["wave"] = pairs.wave.map(WLAB)
PART.to_csv(OUT / "09_panel_participation.csv", index=False, encoding="utf-8-sig")
pairs.to_csv(OUT / "09_panel_participation.csv", index=False, mode="a", encoding="utf-8-sig")


DQ = []
for w in WAVES:
    d = P[P.wave == w]
    a = A[A.wave == w]
    DQ.append({
        "wave": WLAB[w], "rows": len(d), "duplicate_person_rows": int(d.duplicated("ID").sum()),
        "age_missing_pct": round(100 * d.age.isna().mean(), 2), "age_min": d.age.min(), "age_max": d.age.max(),
        "sex_missing_pct": round(100 * d.sex.isna().mean(), 2),
        "weight_missing_pct": round(100 * d.weight.isna().mean(), 2), "crosssection_pct": round(100 * (d.crosssection == 1).mean(), 1),
        "cesd_all_10_items_pct": round(100 * (d.cesd_nmiss == 0).mean(), 1), "cesd_1_2_items_missing_pct": round(100 * d.cesd_nmiss.between(1, 2).mean(), 1),
        "cesd_not_asked_pct": round(100 * (d.cesd_nmiss == 10).mean(), 1),
        "cesd10_mean": round(d.cesd10.mean(), 2), "cesd10_sd": round(d.cesd10.std(), 2), "cesd10_min": d.cesd10.min(), "cesd10_max": d.cesd10.max(),
        "dx_emot_missing_pct": round(100 * d.dx_emot.isna().mean(), 2), "adl_missing_pct": round(100 * d.adl_any.isna().mean(), 2),
        "srh_missing_pct": round(100 * d.srh_poor.isna().mean(), 2), "hukou_missing_pct": round(100 * d.hukou_agri.isna().mean(), 2),
        "proxy_recorded": bool(d.proxy.notna().any()), "interview_years": "/".join(str(int(x)) for x in sorted(d.iyear.dropna().unique())),
        "analytic_n": len(a), "analytic_psu": a.communityID.nunique(), "analytic_weight_sum_millions": round(a.weight.sum() / 1e6, 1),
        "analytic_weight_cv": round(a.weight.std() / a.weight.mean(), 2),
    })
pd.DataFrame(DQ).to_csv(OUT / "08_data_quality_by_wave.csv", index=False, encoding="utf-8-sig")


import textwrap

fig, ax = plt.subplots(figsize=(7.6, 8.8))
ax.set_xlim(0, 100)
ax.set_ylim(0, 114)
ax.axis("off")
DARK, RED, BLUE_FC, BLUE_EC, GREY = "#444444", "#8B1A1A", "#E6EEF7", "#2171B5", "#F4F4F4"
LX, LW = 2, 30
XCOL = np.linspace(38.5, 94.5, 6)
X0, W = 2, 96


def row_box(y, h, title, nums, fc=BLUE_FC, ec=BLUE_EC, sup=""):
    ax.add_patch(FancyBboxPatch((X0, y), W, h, boxstyle="round,pad=0.25,rounding_size=0.7", fc=fc, ec=ec, lw=0.9))
    ax.text(LX + 1.2, y + h / 2, textwrap.fill(title, 34) + sup, ha="left", va="center", fontsize=7, fontweight="bold", linespacing=1.15)
    for x, n in zip(XCOL, nums):
        ax.text(x, y + h / 2, f"{n:,}", ha="center", va="center", fontsize=7.6)


def row_text(y, label, nums, color=RED, fs=6.2, fmt=lambda n: f"−{n:,}" if n else "0", sup=""):
    ax.text(LX + 1.2, y, textwrap.fill(label, 40) + sup, ha="left", va="center", fontsize=fs, color=color, linespacing=1.1)
    for x, n in zip(XCOL, nums):
        ax.text(x, y, fmt(n), ha="center", va="center", fontsize=fs, color=color, bbox=dict(fc="white", ec="none", pad=0.6), zorder=5)


def arrows(y0, y1):
    for x in XCOL:
        ax.annotate("", xy=(x, y1), xytext=(x, y0), arrowprops=dict(arrowstyle="-|>", lw=0.7, color=DARK, shrinkA=0, shrinkB=0, mutation_scale=7))


y = 112
ax.text(LX + 1.2, y, "CHARLS wave", ha="left", va="center", fontsize=7.3, fontweight="bold")
for x, w in zip(XCOL, WAVES):
    ax.text(x, y, WLAB[w], ha="center", va="center", fontsize=7.6, fontweight="bold")
for dy, lab, vals in [(3.0, "CES-D-10 items", [CESD_VARS[w] for w in WAVES]),
                      (5.9, "Age at interview from", ["birth year", "birth year", "birth year\n(ID card)", "birth year\n(ID card)", "xrage", "xrage"]),
                      (8.9, "Weight file", ["weight.dta", "Weights.dta", "Weights.dta", "Weights.dta", "Weights.dta", "2023/Weights.dta"])]:
    ax.text(LX + 1.2, y - dy, lab, ha="left", va="center", fontsize=6.2, color=DARK)
    for x, v in zip(XCOL, vals):
        ax.text(x, y - dy, v, ha="center", va="center", fontsize=6.2, color=DARK)
ax.plot([X0, X0 + W], [y - 10.6, y - 10.6], color=DARK, lw=0.8)


y = 93.5
row_box(y, 6.5, "Respondents in the demographic file (one row per person)", FLOW.respondents, sup="ᵃ")
arrows(y, y - 5.2)
row_text(y - 2.6, "Not asked / no CES-D-10 item answered", FLOW.excl_cesd_not_asked, sup="ᵇ")
y -= 11.7
row_box(y, 6.5, "CES-D-10 module answered (≥1 item)", FLOW.cesd_module_answered)
arrows(y, y - 5.2)
row_text(y - 2.6, "1–9 items missing", FLOW.excl_cesd_partial, sup="ᶜ")
y -= 11.7
row_box(y, 6.5, "All ten CES-D-10 items answered (score 0–30)", FLOW.cesd_complete)
arrows(y, y - 7.6)
row_text(y - 2.6, "Aged <50 y or age missing", FLOW.excl_age_under50_or_missing)
row_text(y - 5.2, "   of whom aged 45–49 y", FLOW.age_45_49_with_cesd, color=DARK, fs=5.9, fmt=lambda n: f"{n:,}", sup="ᵈ")
y -= 14.1
row_box(y, 6.5, "Aged ≥50 years at interview", FLOW.aged_50plus)
arrows(y, y - 7.6)
row_text(y - 2.6, "Sex missing", FLOW.excl_sex_missing)
row_text(y - 5.2, "No cross-sectional weight", FLOW.excl_no_weight_or_not_crosssection, sup="ᵉ")
y -= 14.1
row_box(y, 6.5, "Analytic sample: aged ≥50 y, complete CES-D-10, cross-sectional weight", FLOW.analytic, fc="#CFE0F1")
row_text(y - 2.4, "Communities (PSUs)", FLOW.psu_analytic, color=DARK, fs=6.2, fmt=lambda n: f"{int(n)}")
row_text(y - 4.8, "Weighted population ≥50 y (millions)", FLOW.weighted_population_50plus_millions, color=DARK, fs=6.2, fmt=lambda n: f"{n:.1f}")
row_text(y - 7.2, "With a previous wave (basis of D4)", [0] + list(FLOW.d4_defined[1:]), color=DARK, fs=6.2, fmt=lambda n: f"{int(n):,}" if n else "—")


y -= 11.5
ax.add_patch(FancyBboxPatch((X0, y - 11.5), W, 11.5, boxstyle="round,pad=0.25,rounding_size=0.7", fc=GREY, ec="#666666", lw=0.9))
ax.text(LX + 1.2, y - 1.6, f"Pooled analytic data: {n_pw:,} person-waves from {n_persons:,} persons", ha="left", va="top", fontsize=7.2, fontweight="bold")
part_txt = "   ".join(f"{int(k)}: {int(v):,} ({100*v/part.sum():.0f}%)" for k, v in part.items())
ax.text(LX + 1.2, y - 4.6, "Number of waves per person (1–6): " + part_txt, ha="left", va="top", fontsize=6.2, color=DARK)
ax.text(LX + 1.2, y - 7.2, textwrap.fill("Derived variables: CES-D-10 score and six non-somatic items; case definitions D1–D7; ever doctor-diagnosed emotional/psychiatric problem; ADL limitation; self-rated health; hukou; interview year", 150),
        ha="left", va="top", fontsize=6.0, color=DARK, linespacing=1.2)


y -= 14.5
foot = [
    "ᵃ Wave 6 (2021–2023) was fielded over three years: 19,197 records in the 2021/2022/2023 files → 18,133 after keeping each person's response-year record. 2011 IDs converted to 12 digits.",
    "ᵇ Proxy interviews, break-offs and respondents for whom the depression module was not fielded.",
    "ᶜ Prorated scores (≤2 items missing) are kept only for sensitivity analysis.",
    "ᵈ The 45–49-year group is not used because wave 6 contains only 175 such respondents (9 men): the refresher sample did not replenish the youngest ages.",
    "ᵉ Not in the cross-sectional sample of the wave (wave 6 ≈9%); 2011 has weights for all respondents.",
    "ADL: in 2011–2018 the functional-limitation module was skipped for ~30% of younger, healthier respondents (CES-D-10 ≥10: 13–19% vs 40–48% among those asked); skipped = no limitation.",
]
yy = y
for t in foot:
    txt = textwrap.fill(t, 165)
    ax.text(LX, yy, txt, ha="left", va="top", fontsize=5.6, color=DARK, linespacing=1.1)
    yy -= 2.0 + 1.6 * txt.count("\n")
fig.savefig(OUT / "07_CHARLS_data_flow.pdf")
fig.savefig(OUT / "07_CHARLS_data_flow.png")
plt.close(fig)
print(FLOW[["wave", "respondents", "cesd_module_answered", "cesd_complete", "aged_50plus", "analytic"]].to_string(index=False))
print(f"pooled {n_pw:,} person-waves, {n_persons:,} persons -> {OUT}")
