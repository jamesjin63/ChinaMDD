#!/usr/bin/env python3
"""Harmonise CHARLS 2011, 2013, 2015, 2018, 2020 and 2021–2023 (W6) into one person-wave panel (MS1 V1).

Run:    python3 00_build_charls_panel.py
Input:  ../../data/raw/CHARLS/CHARLS*/raw_dta/*.dta
Output: ../../data/processed/charls_panel_2011_2023.csv   (one row per person-wave)
        ../../data/processed/charls_panel_README.md        (variable crosswalk, written from the code constants)
        ./qc/panel_build_log.csv                           (row counts at each step)

Design: ../../../研究设计_v0.2_GBD与CHARLS中国中老年精神障碍估计偏差评估.md  (§5.1 case definitions, §6.2 variables)
Rules:  CES-D items are aligned by item content, never by variable name (the numbering changed in 2020 and W6).
        Each item 1–4 is recoded 0–3; items 5 (hopeful) and 8 (happy) are reverse-scored; the score is the sum of 10
        items and is missing if any item is missing (sensitivity: ≤2 missing items prorated).
"""

import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import pyreadstat

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)
QC = HERE / "qc"
QC.mkdir(exist_ok=True)
RAW = HERE.parent.parent / "data" / "raw" / "CHARLS"

# ----------------------------------------------------------------------------- crosswalk (item content -> variable)
CESD_ITEMS = ["bothered", "mind", "depressed", "effort", "hopeful", "fearful", "sleep", "happy", "lonely", "getgoing"]
REVERSE = {"hopeful", "happy"}
CESD_VARS = {
    2011: [f"dc{i:03d}" for i in range(9, 19)],
    2013: [f"dc{i:03d}" for i in range(9, 19)],
    2015: [f"dc{i:03d}" for i in range(9, 19)],
    2018: [f"dc{i:03d}" for i in range(9, 19)],
    2020: [f"dc{i:03d}" for i in range(16, 26)],
    2026: [f"dc{i:03d}" for i in range(51, 61)],
}
ADL_VARS = {  # dressing, bathing, eating, bed, toilet (1 = no difficulty; 2–4 = difficulty)
    2011: ["db010", "db011", "db012", "db013", "db014"],
    2013: ["db010", "db011", "db012", "db013", "db014"],
    2015: ["db010", "db011", "db012", "db013", "db014"],
    2018: ["db010", "db011", "db012", "db013", "db014"],
    2020: ["db001", "db003", "db005", "db007", "db009"],
    2026: ["db001", "db003", "db005", "db007", "db009"],
}
# self-reported doctor diagnosis of "emotional, nervous or psychiatric problems" (chronic-disease item 11)
DX_RULE = {
    2011: "da007_11_ == 1",
    2013: "(zda007_11_ == 1 & da007_w2_1_11_ == 1) | da007_w2_2_11_ == 1 | da007_11_ == 1",
    2015: "(zda007_11_ == 1 & da007_w2_1_11_ == 1) | da007_w2_2_11_ == 1 | da007_11_ == 1",
    2018: "da007_11_ == 1",
    2020: "da003_11_ == 1 | da002_11_ in (1, 2, 3)",
    2026: "da011_11_ == 1 | da012_11_ in (1, 2, 3)",
}
AGE_RULE = {  # wave-reported birth year/month; the panel then uses ONE person-level birth year (mode across waves)
    2011: "birth year/month ba002_1/ba002_2",
    2013: "ba002_1/ba002_2 if asked else preloaded zba002_1/zba002_2",
    2015: "actual ba002_1/ba002_2 if asked else ID-card ba004_w3_1/ba004_w3_2",
    2018: "actual ba002_1/ba002_2 if asked else ID-card ba004_w3_1/ba004_w3_2",
    2020: "actual ba003_1/ba003_2 only (157 people). NOT zrbirthyear/xrage: in the 2020 release zrbirthyear is shifted +2 y for 90% of respondents and xrage = 2020 − zrbirthyear is 2 y too low",
    2026: "actual ba006_1/ba006_2 else ID-card ba004_1/ba004_2 else zrbirthyear (xrage kept for reference only)",
}
AGE_FORMULA = "age = iyear − byear − 1[imonth < bmonth]; byear/bmonth = most frequent value reported for the person across waves (ties → latest wave)"
WEIGHT_VAR = {2011: "ind_weight_ad2", 2013: "INDV_weight_ad2", 2015: "INDV_weight_ad2",
              2018: "INDV_weight_ad2", 2020: "INDV_weight_ad2", 2026: "INDV_weight_ad2"}
HUKOU_RULE = {
    2011: "bc001", 2013: "bc001 if asked else zbc001", 2015: "bc002_w3_1 (changed) else bc001_w3_2 (last) ",
    2018: "bc002_w3_1 (changed) else zbc004 (record)", 2020: "ba009", 2026: "xrhukoutype",
}
SRH_RULE = {2011: "da001/da002 (random split; poor = 5 on da001, 4–5 on da002)",
            2013: "da001/da002 (as 2011)", 2015: "da001/da002 (as 2011)",
            2018: "da002 (4–5 = poor/very poor)", 2020: "da001 (4–5)", 2026: "da001 (4–5)"}
PSY_TREAT = {2011: "da020s1–s3", 2013: "da020s1–s3", 2015: "da020s1–s3", 2018: "da020_w4_s1–s3",
             2020: "not asked", 2026: "not asked (sleeping pills only)"}

LOG = []


def log(wave, step, n):
    LOG.append({"wave": wave, "step": step, "rows": int(n)})
    print(f"  [{wave}] {step}: {n:,}")


def rd(path, cols=None):
    """Read a .dta keeping only `cols` (silently dropping those not present); labelled values -> numbers."""
    _, meta = pyreadstat.read_dta(str(path), metadataonly=True)
    keep = [c for c in cols if c in meta.column_names] if cols else None
    df, _ = pyreadstat.read_dta(str(path), usecols=keep, apply_value_formats=False)
    for c in df.columns:
        if c in ("ID", "householdID", "communityID", "iyear", "imonth"):
            df[c] = df[c].astype(str).str.strip()
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def num(df, c):
    return df[c] if c in df else pd.Series(np.nan, index=df.index)


def id_2011_to_12(s):
    s = s.astype(str)
    return s.str[:9] + "0" + s.str[9:]


def cesd_block(df, vars_):
    """Return 10 recoded items (0–3), the complete-case score and the prorated score (≤2 missing)."""
    items = pd.DataFrame(index=df.index)
    for name, v in zip(CESD_ITEMS, vars_):
        x = num(df, v)
        x = x.where(x.between(1, 4))            # 997/999/8/9 = DK/RF -> missing
        items[f"cesd_{name}"] = (4 - x) if name in REVERSE else (x - 1)
    nmiss = items.isna().sum(axis=1)
    score = items.sum(axis=1, min_count=10)
    pror = (items.mean(axis=1) * 10).where(nmiss <= 2).round(2)
    items["cesd10"] = score
    items["cesd10_prorated"] = pror
    items["cesd_nmiss"] = nmiss
    # non-somatic sub-score (6 items: bothered, depressed, hopeful, fearful, happy, lonely)
    nons = [f"cesd_{k}" for k in ("bothered", "depressed", "hopeful", "fearful", "happy", "lonely")]
    items["cesd6_nonsomatic"] = items[nons].sum(axis=1, min_count=6)
    # 8 negatively worded items (drops the two reversed positive items hopeful, happy), 0–24
    neg = [f"cesd_{k}" for k in CESD_ITEMS if k not in REVERSE]
    items["cesd8_negative"] = items[neg].sum(axis=1, min_count=8)
    return items


def adl_block(df, vars_):
    m = pd.DataFrame({v: num(df, v) for v in vars_})
    m = m.where((m >= 1) & (m <= 4))
    any_diff = (m >= 2).any(axis=1)
    # In 2011–2018 the whole functional-limitation module (DB001–DB014) was skipped for ~30% of respondents, who are
    # younger, healthier and far less depressed (checked 2026-11-12: CES-D≥10 13–19% vs 40–48% among those asked).
    # A fully skipped module is therefore coded as "no ADL limitation"; in 2020 and W6 the items were asked of everyone.
    return any_diff.astype(float)


def srh_poor(df, wave):
    if wave in (2011, 2013, 2015):
        a, b = num(df, "da001"), num(df, "da002")
        out = pd.Series(np.nan, index=df.index)
        out[a.between(1, 5)] = (a[a.between(1, 5)] == 5).astype(float)
        out[b.between(1, 5)] = (b[b.between(1, 5)] >= 4).astype(float)
        return out
    v = num(df, "da002" if wave == 2018 else "da001")
    return (v >= 4).astype(float).where(v.between(1, 5))


def dx_block(df, wave):
    g = lambda c: num(df, c)
    if wave == 2011:
        yes, asked = g("da007_11_") == 1, g("da007_11_").between(1, 2)
    elif wave in (2013, 2015):
        yes = ((g("zda007_11_") == 1) & (g("da007_w2_1_11_") == 1)) | (g("da007_w2_2_11_") == 1) | (g("da007_11_") == 1)
        asked = g("da007_w2_1_11_").between(1, 2) | g("da007_w2_2_11_").between(1, 2) | g("da007_11_").between(1, 2)
    elif wave == 2018:
        yes, asked = g("da007_11_") == 1, g("da007_11_").between(1, 2)
    elif wave == 2020:
        yes = (g("da003_11_") == 1) | g("da002_11_").isin([1, 2, 3])
        asked = g("da003_11_").between(1, 2) | g("da002_11_").isin([1, 2, 3, 99])
    else:
        yes = (g("da011_11_") == 1) | g("da012_11_").isin([1, 2, 3])
        asked = g("da011_11_").between(1, 2) | g("da012_11_").isin([1, 2, 3, 99])
    return yes.astype(float).where(asked)


def treat_block(df, wave):
    if wave in (2011, 2013, 2015):
        cols = ["da020s1", "da020s2", "da020s3"]
    elif wave == 2018:
        cols = ["da020_w4_s1", "da020_w4_s2", "da020_w4_s3"]
    else:
        return pd.Series(np.nan, index=df.index)
    m = pd.DataFrame({c: num(df, c) for c in cols})
    return (m.notna() & (m > 0)).any(axis=1).astype(float).where(m.notna().any(axis=1))


def hukou_block(df, wave):
    g = lambda c: num(df, c)
    if wave == 2011:
        h = g("bc001")
    elif wave == 2013:
        h = g("bc001").fillna(g("zbc001"))
    elif wave == 2015:
        h = g("bc002_w3_1").fillna(g("bc001_w3_2"))
    elif wave == 2018:
        h = g("bc002_w3_1").fillna(g("zbc004"))
    elif wave == 2020:
        h = g("ba009")
    else:
        h = g("xrhukoutype")
    # 1 agricultural, 2 non-agricultural, 3 unified residence, 4 none -> agricultural (rural hukou) flag
    return pd.Series(np.where(h.isin([1, 2, 3, 4]), (h == 1).astype(float), np.nan), index=df.index)


# ----------------------------------------------------------------------------- per-wave builders
def build_2011():
    w = 2011
    d = RAW / "CHARLS2011" / "raw_dta"
    demo = rd(d / "demographic_background.dta", ["ID", "householdID", "communityID", "rgender", "ba002_1", "ba002_2", "bc001", "proxy"])
    hs = rd(d / "health_status_and_functioning.dta", ["ID"] + CESD_VARS[w] + ADL_VARS[w] +
            ["da007_11_", "da001", "da002", "da020s1", "da020s2", "da020s3", "proxy"])
    wt = rd(d / "weight.dta", ["ID", "ind_weight_ad2", "iyear", "imonth", "mainr"])
    psu = rd(d / "psu.dta", ["communityID", "urban_nbs"])
    log(w, "demographic rows", len(demo))
    df = demo.merge(hs.drop(columns=["proxy"], errors="ignore"), on="ID", how="left").merge(wt, on="ID", how="left")
    df = df.merge(psu, on="communityID", how="left")
    log(w, "after merges", len(df))
    iy = pd.to_numeric(df["iyear"], errors="coerce")
    out = pd.DataFrame({
        "ID": id_2011_to_12(df["ID"]), "communityID": df["communityID"], "wave": w, "wave_label": "2011",
        "iyear": iy, "imonth": pd.to_numeric(df["imonth"], errors="coerce"),
        "byear_wave": num(df, "ba002_1"), "bmonth_wave": num(df, "ba002_2"), "xrage_charls": np.nan,
        "sex_wave": num(df, "rgender").where(num(df, "rgender").isin([1, 2])),
        "weight": df["ind_weight_ad2"], "crosssection": 1.0, "died": 0.0,
        "proxy": num(df, "proxy"), "urban_nbs": df["urban_nbs"],
    })
    return finish(out, df, w)


def build_follow(w, folder, demo_file, hs_file, cog_file, wt_file, si_file):
    d = RAW / folder / "raw_dta"
    demo_cols = ["ID", "householdID", "communityID", "ba000_w2_3", "xrgender", "xrage", "ba002_1", "ba002_2", "zba002_1", "zba002_2",
                 "ba004_w3_1", "ba004_w3_2", "ba003_1", "ba003_2", "ba005_w4", "bc001", "zbc001", "bc001_w3_2", "bc002_w3_1", "zbc004", "ba009", "ba011",
                 "be001", "bd001", "zbd001"]
    hs_cols = ["ID", "xrgender", "xrage"] + ADL_VARS[w] + ["da007_11_", "zda007_11_", "da007_w2_1_11_", "da007_w2_2_11_",
               "da003_11_", "da002_11_", "da001", "da002", "da020s1", "da020s2", "da020s3", "da020_w4_s1",
               "da020_w4_s2", "da020_w4_s3", "proxy"]
    demo = rd(d / demo_file, demo_cols)
    hs = rd(d / hs_file, hs_cols + (CESD_VARS[w] if cog_file is None else []))
    log(w, "demographic rows", len(demo))
    df = demo.merge(hs, on="ID", how="left", suffixes=("", "_hs"))
    if cog_file is not None:
        cog = rd(d / cog_file, ["ID"] + CESD_VARS[w])
        df = df.merge(cog, on="ID", how="left")
    wt = rd(d / wt_file, ["ID", WEIGHT_VAR[w], "iyear", "imonth", "crosssection"]).drop_duplicates("ID")
    df = df.merge(wt, on="ID", how="left")
    if si_file is not None:
        si = rd(d / si_file, ["ID", "iyear", "imonth", "crosssection", "died"]).drop_duplicates("ID")
        df = df.merge(si, on="ID", how="left", suffixes=("", "_si"))
        for c in ("iyear", "imonth", "crosssection", "died"):
            if c + "_si" in df:
                df[c] = df[c].where(df[c].notna() & (df[c].astype(str) != "nan"), df[c + "_si"]) if c in df else df[c + "_si"]
    log(w, "after merges", len(df))
    iy = pd.to_numeric(df["iyear"], errors="coerce")
    if w == 2013:
        by, bm = num(df, "ba002_1").fillna(num(df, "zba002_1")), num(df, "ba002_2").fillna(num(df, "zba002_2"))
    elif w in (2015, 2018):
        by, bm = num(df, "ba002_1").fillna(num(df, "ba004_w3_1")), num(df, "ba002_2").fillna(num(df, "ba004_w3_2"))
    else:  # 2020: only the actually re-asked birth date is trustworthy (see AGE_RULE)
        by, bm = num(df, "ba003_1"), num(df, "ba003_2")
    sex = num(df, "xrgender").fillna(num(df, "ba000_w2_3")).fillna(num(df, "xrgender_hs"))
    out = pd.DataFrame({
        "ID": df["ID"], "communityID": df["communityID"], "wave": w, "wave_label": str(w),
        "iyear": iy, "imonth": pd.to_numeric(df["imonth"], errors="coerce"),
        "byear_wave": by, "bmonth_wave": bm, "xrage_charls": num(df, "xrage"),
        "sex_wave": sex.where(sex.isin([1, 2])),
        "weight": df[WEIGHT_VAR[w]], "crosssection": num(df, "crosssection"), "died": num(df, "died").fillna(0),
        "proxy": num(df, "proxy"), "urban_nbs": np.nan,
    })
    return finish(out, df, w)


def build_w6():
    w = 2026
    d = RAW / "CHARLS2026" / "raw_dta"
    si = rd(d / "2023" / "Sample_Infor.dta", ["ID", "res_wave", "crosssection", "died", "iyear", "imonth"])
    wt = rd(d / "2023" / "Weights.dta", ["ID", "INDV_weight_ad2", "INDV_weight_post2"])
    parts = []
    for y in (2021, 2022, 2023):
        demo = rd(d / str(y) / "Demographics.dta", ["ID", "householdID", "communityID", "xrgender", "xrage", "xrhukoutype", "bd001",
                                                     "ba004_1", "ba004_2", "ba006_1", "ba006_2", "zrbirthyear"])
        cog = rd(d / str(y) / "Cognition_Depression.dta", ["ID"] + CESD_VARS[w] + ["proxy"])
        hs = rd(d / str(y) / "Health_Status_and_Functioning.dta",
                ["ID", "xrage", "xrgender", "da011_11_", "da012_11_", "da001"] + ADL_VARS[w] + ["proxy"])
        df = demo.merge(cog.rename(columns={"proxy": "proxy_cog"}), on="ID", how="left")
        df = df.merge(hs, on="ID", how="left", suffixes=("", "_hs"))
        df["file_year"] = y
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)
    log(w, "three file-years stacked", len(df))
    df = df.merge(si, on="ID", how="left")
    df = df[df["file_year"] == df["res_wave"]].copy()
    log(w, "kept record of the response year (res_wave)", len(df))
    df = df.merge(wt, on="ID", how="left")
    iy = pd.to_numeric(df["iyear"], errors="coerce").fillna(df["res_wave"])
    sex = num(df, "xrgender").fillna(num(df, "xrgender_hs"))
    out = pd.DataFrame({
        "ID": df["ID"], "communityID": df["communityID"], "wave": w, "wave_label": "2021–2023",
        "iyear": iy, "imonth": pd.to_numeric(df["imonth"], errors="coerce"),
        "byear_wave": num(df, "ba006_1").fillna(num(df, "ba004_1")).fillna(num(df, "zrbirthyear")),
        "bmonth_wave": num(df, "ba006_2").fillna(num(df, "ba004_2")),
        "xrage_charls": num(df, "xrage").fillna(num(df, "xrage_hs")),
        "sex_wave": sex.where(sex.isin([1, 2])),
        "weight": df["INDV_weight_ad2"], "weight_post": df["INDV_weight_post2"],
        "crosssection": num(df, "crosssection"), "died": num(df, "died").fillna(0),
        "proxy": num(df, "proxy").fillna(num(df, "proxy_cog").where(num(df, "proxy_cog") == 1)), "urban_nbs": np.nan,
    })
    return finish(out, df, w)


def finish(out, df, w):
    out = pd.concat([out, cesd_block(df, CESD_VARS[w])], axis=1)
    out["adl_any"] = adl_block(df, ADL_VARS[w])
    out["srh_poor"] = srh_poor(df, w)
    out["dx_emot"] = dx_block(df, w)
    out["psy_treat"] = treat_block(df, w)
    out["hukou_agri"] = hukou_block(df, w)
    # 2011/2015: 0/1 for everyone; 2020/W6: flag only present (=1) for proxy interviews; 2013/2018: not available
    out["proxy"] = (out["proxy"] == 1).astype(float) if w in (2011, 2015, 2020, 2026) else np.nan
    out["byear_wave"] = out["byear_wave"].where(out["byear_wave"].between(1890, 2005))
    out["bmonth_wave"] = out["bmonth_wave"].where(out["bmonth_wave"].between(1, 12))
    log(w, "persons with complete CES-D-10", out["cesd10"].notna().sum())
    return out


# ----------------------------------------------------------------------------- run
print("Building CHARLS panel …")
panel = pd.concat([
    build_2011(),
    build_follow(2013, "CHARLS2013", "Demographic_Background.dta", "Health_Status_and_Functioning.dta", None, "Weights.dta", None),
    build_follow(2015, "CHARLS2015", "Demographic_Background.dta", "Health_Status_and_Functioning.dta", None, "Weights.dta", "Sample_Infor.dta"),
    build_follow(2018, "CHARLS2018", "Demographic_Background.dta", "Health_Status_and_Functioning.dta", "Cognition.dta", "Weights.dta", "Sample_Infor.dta"),
    build_follow(2020, "CHARLS2020", "Demographic_Background.dta", "Health_Status_and_Functioning.dta", None, "Weights.dta", "Sample_Infor.dta"),
    build_w6(),
], ignore_index=True)

panel = panel.sort_values(["ID", "wave"]).reset_index(drop=True)
dup = panel.duplicated(["ID", "wave"]).sum()
assert dup == 0, f"duplicate person-wave rows: {dup}"


def person_mode(df, col):
    """Most frequent non-missing value per person; ties broken by the latest wave reporting that value."""
    x = df[["ID", "wave", col]].dropna(subset=[col])
    cnt = x.groupby(["ID", col]).agg(n=("wave", "size"), last=("wave", "max")).reset_index()
    cnt = cnt.sort_values(["ID", "n", "last"], ascending=[True, False, False]).drop_duplicates("ID")
    return df["ID"].map(cnt.set_index("ID")[col])


# one birth year / month and one sex per person
panel["byear"] = person_mode(panel, "byear_wave")
panel["bmonth"] = person_mode(panel, "bmonth_wave")
panel["sex"] = person_mode(panel, "sex_wave")
n_noby = panel.loc[panel.byear.isna(), "ID"].nunique()
print(f"  persons without any reported birth year: {n_noby:,} (age set missing; 2020 xrage not used)")
# exact age at interview: subtract one year if the interview month precedes the birth month
before_bday = (panel["imonth"] < panel["bmonth"]) & panel["imonth"].notna() & panel["bmonth"].notna()
panel["age"] = (panel["iyear"] - panel["byear"] - before_bday.astype(int)).where(panel["byear"].notna())
panel["age"] = panel["age"].where(panel["age"].between(18, 115))
# ever told by a doctor (carry forward within person: once yes, always yes)
dx0 = panel["dx_emot"].fillna(0)
ever = dx0.groupby(panel["ID"]).cummax()
panel["dx_emot_ever"] = np.where(panel["dx_emot"].isna() & (ever == 0), np.nan, ever)
# persistent symptoms (D4): CES-D-10 ≥10 in this wave AND in the immediately preceding wave (adjacent waves only)
ORDER = {2011: 0, 2013: 1, 2015: 2, 2018: 3, 2020: 4, 2026: 5}
prev = panel.groupby("ID")["cesd10"].shift(1)
prev_wave = panel.groupby("ID")["wave"].shift(1)
panel["cesd10_prev"] = prev
panel["wave_prev"] = prev_wave
adjacent = (panel["wave"].map(ORDER) - prev_wave.map(ORDER)) == 1
panel["d4_any_prev"] = np.where(panel["cesd10"].notna() & prev.notna(), ((panel["cesd10"] >= 10) & (prev >= 10)).astype(float), np.nan)
panel["d4_persistent"] = panel["d4_any_prev"].where(adjacent)
for w in (2011, 2013, 2015, 2018, 2020, 2026):
    m = panel.wave == w
    log(w, "persons aged ≥50 with CES-D-10, weight and sex", int((m & panel.cesd10.notna() & (panel.age >= 50) & panel.weight.notna() & panel.sex.notna()).sum()))

panel.to_csv(OUT / "charls_panel_2011_2023.csv", index=False)
pd.DataFrame(LOG).to_csv(QC / "panel_build_log.csv", index=False)
print(f"\nPanel: {len(panel):,} person-waves, {panel.ID.nunique():,} persons -> {OUT / 'charls_panel_2011_2023.csv'}")

# ----------------------------------------------------------------------------- README (variable crosswalk)
rows = []
for w in (2011, 2013, 2015, 2018, 2020, 2026):
    rows.append({"Wave": {2026: "2021–2023 (W6)"}.get(w, str(w)), "CES-D-10 items": f"{CESD_VARS[w][0]}–{CESD_VARS[w][-1]}",
                 "Age": AGE_RULE[w], "Diagnosis (item 11)": DX_RULE[w], "ADL (5 items)": ", ".join(ADL_VARS[w]),
                 "Self-rated health": SRH_RULE[w], "Hukou": HUKOU_RULE[w], "Psychiatric treatment": PSY_TREAT[w],
                 "Weight": WEIGHT_VAR[w]})
cw = pd.DataFrame(rows)
cw.to_csv(OUT / "charls_variable_crosswalk.csv", index=False)
md = ["# CHARLS 2011–2023 person-wave panel (MS1 V1)", "",
      "Built by `V1/09_代码与质控_Code_QC/00_build_charls_panel.py`. One row per person-wave; 2011 IDs converted to 12 digits.", "",
      "## Variable crosswalk", "", cw.to_markdown(index=False), "",
      "## Derived variables", "",
      "| Column | Definition |", "|---|---|",
      "| `cesd_<item>` | item recoded 0–3 (1–4 → 0–3; hopeful and happy reversed) |",
      "| `cesd10` | sum of 10 items, missing if any item missing |",
      "| `cesd10_prorated` | mean × 10 when ≤2 items missing (sensitivity) |",
      "| `cesd6_nonsomatic` | sum of bothered, depressed, hopeful, fearful, happy, lonely (0–18) |",
      "| `cesd8_negative` | sum of the eight negatively worded items, i.e. without the reversed items hopeful and happy (0–24); sensitivity for the 2013/2020 anomaly of the positive items |",
      "| `d4_persistent` | CES-D-10 ≥10 in this wave and in the immediately preceding wave (adjacent waves only); `d4_any_prev` relaxes adjacency |",
      "| `byear`, `bmonth`, `age` | person-level birth year/month (mode across waves; 2020's shifted preload excluded) and exact age at interview: " + AGE_FORMULA + " |",
      "| `byear_wave`, `bmonth_wave`, `xrage_charls` | the raw wave-specific birth year/month and CHARLS's own xrage (2020 xrage is 2 y too low) |",
      "| `sex` | person-level sex (mode across waves); `sex_wave` is the raw wave value |",
      "| `dx_emot_ever` | `dx_emot` carried forward within person (once reported, always 1) — used for D6 |",
      "| `adl_any` | difficulty in any of dressing, bathing, eating, bed transfer, toileting |",
      "| `srh_poor` | self-rated health poor/very poor |",
      "| `dx_emot` | ever told by a doctor of emotional, nervous or psychiatric problems (lifetime, with follow-up verification) |",
      "| `psy_treat` | currently receiving psychiatric/psychological treatment or medication (2011–2018 only) |",
      "| `hukou_agri` | agricultural hukou |",
      "| `weight` | cross-sectional individual weight with household and individual non-response adjustment |",
      "| `weight_post` | W6 post-stratification weight (age × sex), sensitivity only |",
      "| `iyear` | interview year (W6: 2021, 2022 or 2023 from Sample_Infor) |", ""]
(OUT / "charls_panel_README.md").write_text("\n".join(md), encoding="utf-8")
print("README written.")
