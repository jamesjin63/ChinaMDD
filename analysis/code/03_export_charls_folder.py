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
md = f"""# CHARLS 2011–2023 精神健康（抑郁）整理数据

> 生成日期：2026-11-12。由 `code/03_export_charls_folder.py` 从 MS1 的处理结果导出；原始 `.dta` 在 `data/raw/CHARLS/`，清洗脚本见 `code/00_build_charls_panel.py`。
> 对应研究设计：`../研究设计_v0.2_GBD与CHARLS中国中老年精神障碍估计偏差评估.md`；分析产出：`../MS1_GBD_vs_CHARLS/V1/`。

## 文件

| 文件 | 内容 | 行数 |
|---|---|---:|
| `01_charls_mental_health_panel_2011_2023.csv` | 六轮全部受访者的人次面板（每人每轮一行），CES-D-10 逐条目与总分、自报精神疾病诊断、治疗、ADL、自评健康、年龄、性别、权重、PSU | {len(P1):,} |
| `02_charls_analytic_50plus_with_definitions.csv` | MS1 分析样本：≥50 岁、CES-D 十项齐全、有截面权重；附病例定义 D1–D7 和 5 岁年龄组 | {len(A):,} |
| `03_summary_by_wave_sex.csv` | 各定义的加权患病率，按轮次 × 性别 | {len(s3):,} |
| `04_summary_by_wave_sex_age.csv` | 同上，再按 5 岁年龄组 | — |
| `05_codebook.csv` | 文件 01/02 的逐列说明 | — |
| `06_variable_crosswalk_by_wave.csv` | 每一轮用了哪些原始变量（CES-D、年龄、诊断、ADL、自评健康、户口、治疗、权重） | 6 |
| `07_CHARLS_data_flow.pdf` / `.png` | 样本推导流程图（逐轮：受访者 → 答过 CES-D → 十项齐全 → ≥50 岁 → 有权重），含每步排除人数 | — |
| `07_CHARLS_data_flow_counts.csv` | 流程图中的全部数字 | 6 |
| `08_data_quality_by_wave.csv` | 逐轮数据质量：重复 ID、年龄/性别/权重缺失、CES-D 缺失模式、分数范围、各变量缺失率、权重变异 | 6 |
| `09_panel_participation.csv` | 每人参加的轮数分布；各轮可定义 D4 的人次 | — |
| `CHARLS数据清洗手册.md` | **下次提取其他变量先读这个**：数据位置、读取方法、ID 转换、W6 三年合一、各轮基础变量来源、预载/核对题型、跳问、质控清单、已知的坑 | — |
| `code/` | 清洗、导出与流程图脚本（`00_build_charls_panel.py`、`03_export_charls_folder.py`、`04_charls_flow_diagram.py`） | — |

## 样本量

| 轮次 | 面板人次（文件 01） | 分析样本 ≥50 岁（文件 02） |
|---|---:|---:|
""" + "\n".join(f"| {w} | {n_wave[w]:,} | {n_an.get(w, 0):,} |" for w in ["2011", "2013", "2015", "2018", "2020", "2021–2023"]) + f"""

## 病例定义（设计 §5.1）

| 编码 | 定义 | 列名 |
|---|---|---|
| D1 | CES-D-10 ≥10（当前抑郁症状，常用口径） | `D1_cesd10_ge10` |
| D2 | CES-D-10 ≥12 | `D2_cesd10_ge12` |
| D3 | CES-D-10 ≥15（中重度） | `D3_cesd10_ge15` |
| D4 | 相邻两轮都 ≥10（持续性症状；2013 起可定义） | `D4_persistent` |
| D5 | ≥10 且任一 ADL 受限 | `D5_ge10_with_ADL` |
| D6 | 自报医生诊断“情感及精神问题”（终生，跨轮前推：报过一次即为 1） | `D6_self_reported_dx` |
| D7 | ≥10 且无 D6 | `D7_ge10_without_dx` |
| C | CES-D-10 连续分 0–30 | `cesd10` |

CES-D-10 条目按**内容**跨轮对齐：2011–2018 `dc009–dc018`，2020 `dc016–dc025`，第六轮 `dc051–dc060`；第 5 条（对未来有希望）和第 8 条（愉快）反向计分；总分要求十项齐全（`cesd10_prorated` 允许 ≤2 项缺失）。

## 加权患病率一览（≥50 岁，男女合计，%）

{s3b.to_markdown(index=False)}

## 使用时必须知道的几点

1. **第六轮（2021–2023）45–49 岁只有 175 人（男 9 人）**，补充样本没有补足最年轻年龄段；因此文件 02 和所有汇总都从 50 岁起。需要 45–49 岁时只能用 2011–2020（文件 01 里有）。
2. **ADL 跳问**：2011–2018 年整个功能受限模块（DB001–DB014）对约 30% 更年轻、更健康的受访者未问（这部分人 CES-D≥10 只有 13–19%），已按“跳问 = 无受限”编码。
3. **第六轮三年合一**：每人只保留 `res_wave` 对应年份的记录；`iyear` 给出实际访谈年（68% 在 2021 年）。与 GBD 等年度数据比较时按访谈年份匹配。
4. **自报诊断是终生口径**，不是时点患病；2013/2015 合并了预载记录、核对题和补问题，2020 和第六轮合并了新问与“上轮已患”题。
5. **权重**：横截面个人权重（家户+个人无应答调整）；第六轮约 9% 非截面样本无权重，不在文件 02 中。方差估计用 `communityID` 作 PSU。
6. **治疗变量**（`psy_treat`）只在 2011–2018 有，且仅问自报诊断者，样本很小。
7. 2011 年 ID 已转换为 12 位，可直接与后续各轮按 `ID` 衔接。

## 重新生成

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
