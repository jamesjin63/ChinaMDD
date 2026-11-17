#!/usr/bin/env python3
"""Build Nature Medicine-style three-line DOCX tables from analysis/04_Tables/*.csv and verify them.

Run after 01_run_analysis.py:  python3 02_build_tables_docx.py
The CSV is the single source: cells are read as display strings and written verbatim.
Columns named "Group: sub" become a two-level header; other columns are vertically merged labels.
After writing, each DOCX is re-opened and compared cell by cell with its CSV (differences must be 0).
"""

import csv
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Twips

OUT = Path(__file__).resolve().parent
MAIN = OUT.parent / "04_Tables"  # CSV source and DOCX output live together
DOCX_DIR = MAIN

PAGE_W, PAGE_H, MARGIN = 16838, 11906, 720  # A4 landscape, 0.5 inch margins (DXA)
USABLE = PAGE_W - 2 * MARGIN
FONT = "Times New Roman"
# label-column widths (DXA); remaining width is shared equally by numeric columns
LABEL_W = {"Characteristic": 4600, "Source": 1000, "Case definition": 3400, "Planning base": 2900}
GROUP_TEXT_W = {}  # text sub-columns inside a header group
GROUP_FIXED_W = {}  # sub-columns needing a fixed width
UI_RE = re.compile(r"^(.+) \((.+) to (.+)\)$")  # "estimate (low to high)" -> two lines, en dash


def display_key(v):
    """Logical text after the documented display change (interval on line 2, ' to ' -> en dash)."""
    m = UI_RE.match(v)
    return f"{m.group(1)}({m.group(2)}\u2013{m.group(3)})" if m else v


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    header, body = rows[0], rows[1:]
    for i, r in enumerate(body, 2):
        if len(r) != len(header):
            raise SystemExit(f"{path.name}: line {i} has {len(r)} fields, header has {len(header)}")
    return header, body


def split(col):
    return col.split(": ", 1) if ": " in col else (None, col)


def set_cell_border(cell, **edges):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge, sz in edges.items():
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")


def set_width(cell, w):
    tc_pr = cell._tc.get_or_add_tcPr()
    tcw = tc_pr.find(qn("w:tcW"))
    if tcw is None:
        tcw = OxmlElement("w:tcW")
        tc_pr.insert(0, tcw)
    tcw.set(qn("w:w"), str(w))
    tcw.set(qn("w:type"), "dxa")


def write_text(cell, text, size, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.CENTER):
    p = cell.paragraphs[0]
    p.alignment = align
    pf = p.paragraph_format
    pf.space_before = pf.space_after = Pt(1)
    pf.line_spacing = Pt(12) if size >= 8 else Pt(10)
    m = UI_RE.match(text)
    parts = [m.group(1), f"({m.group(2)}\u2013{m.group(3)})"] if m else [text]
    for k, part in enumerate(parts):
        run = p.add_run(part)
        run.font.name = FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        run.font.size = Pt(size)
        run.bold, run.italic = bold, italic
        if k < len(parts) - 1:
            run.add_break()
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def para(doc, text, size, bold=False, italic=False, before=0, after=0, keep=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.keep_with_next = keep
    run = p.add_run(text)
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    run.font.size = Pt(size)
    run.bold, run.italic = bold, italic
    return p


def column_widths(header):
    fixed = {}
    for j, col in enumerate(header):
        grp, sub = split(col)
        if grp is None:
            if col in LABEL_W:
                fixed[j] = LABEL_W[col]
        elif sub in GROUP_FIXED_W:
            fixed[j] = GROUP_FIXED_W[sub]
    free = [j for j in range(len(header)) if j not in fixed]
    share = (USABLE - sum(fixed.values())) // len(free)
    widths = [fixed.get(j, share) for j in range(len(header))]
    widths[free[-1]] += USABLE - sum(widths)  # absorb rounding so widths sum exactly to the page
    assert sum(widths) == USABLE
    return widths


def build(csv_path, title, note):
    header, body = read_csv(csv_path)
    widths = column_widths(header)
    groups = [split(c)[0] for c in header]

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Twips(PAGE_W), Twips(PAGE_H)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Twips(MARGIN))

    para(doc, title, 9, bold=True, after=4, keep=True)
    table = doc.add_table(rows=2 + len(body), cols=len(header))
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    for tag, attrs in (("w:tblW", {"w:w": str(USABLE), "w:type": "dxa"}),
                       ("w:tblInd", {"w:w": "0", "w:type": "dxa"}),
                       ("w:tblLayout", {"w:type": "fixed"})):
        el = tbl_pr.find(qn(tag))
        if el is None:
            el = OxmlElement(tag)
            tbl_pr.append(el)
        for k, v in attrs.items():
            el.set(qn(k), v)
    mar = OxmlElement("w:tblCellMar")
    for edge, w in (("left", 60), ("right", 60), ("top", 20), ("bottom", 20)):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:w"), str(w))
        e.set(qn("w:type"), "dxa")
        mar.append(e)
    tbl_pr.append(mar)
    grid = tbl.tblGrid
    for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
        gc.set(qn("w:w"), str(w))

    for i, row in enumerate(table.rows):
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
        if i < 2:
            tr_pr.append(OxmlElement("w:tblHeader"))  # repeat header rows on every page
        for j, cell in enumerate(row.cells):
            set_width(cell, widths[j])

    # header text (before merging so every cell gets its width)
    for j, col in enumerate(header):
        grp, sub = split(col)
        if grp is None:
            write_text(table.cell(0, j), col, 8, bold=True,
                       align=WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER)
        else:
            write_text(table.cell(1, j), sub, 8, bold=True)
    # body
    for i, r in enumerate(body):
        for j, v in enumerate(r):
            text_col = (groups[j] is None and header[j] in LABEL_W) or split(header[j])[1] in GROUP_TEXT_W
            write_text(table.cell(2 + i, j), v, 7.5,
                       align=WD_ALIGN_PARAGRAPH.LEFT if text_col else WD_ALIGN_PARAGRAPH.CENTER)

    # borders: thick top, thin rule under each group, rule under header, thick bottom
    last = len(table.rows) - 1
    for j in range(len(header)):
        set_cell_border(table.cell(0, j), top=12)
        set_cell_border(table.cell(1, j), bottom=6)
        set_cell_border(table.cell(last, j), bottom=12)
        if groups[j] is not None:
            set_cell_border(table.cell(0, j), bottom=4)

    # merges: label columns vertically, group headers horizontally
    for j, grp in enumerate(groups):
        if grp is None:
            table.cell(0, j).merge(table.cell(1, j))
    j = 0
    while j < len(header):
        if groups[j] is None:
            j += 1
            continue
        k = j
        while k + 1 < len(header) and groups[k + 1] == groups[j]:
            k += 1
        merged = table.cell(0, j).merge(table.cell(0, k))
        for p in merged.paragraphs[1:]:
            p._element.getparent().remove(p._element)
        write_text(merged, groups[j], 8, bold=True)
        j = k + 1

    para(doc, note, 7.5, italic=True, before=4)
    out = DOCX_DIR / (csv_path.stem + ".docx")
    doc.save(out)
    return out, header, body


def logical_matrix(docx_path, ncols):
    """Re-read the first table, expanding gridSpan and filling vertical merges down."""
    t = Document(docx_path).tables[0]._tbl
    rows = []
    for tr in t.findall(qn("w:tr")):
        cells = []
        for tc in tr.findall(qn("w:tc")):
            text = "".join(x.text or "" for x in tc.iter(qn("w:t")))
            tc_pr = tc.find(qn("w:tcPr"))
            span = 1
            vmerge = None
            if tc_pr is not None:
                gs = tc_pr.find(qn("w:gridSpan"))
                span = int(gs.get(qn("w:val"))) if gs is not None else 1
                vm = tc_pr.find(qn("w:vMerge"))
                vmerge = (vm.get(qn("w:val")) or "continue") if vm is not None else None
            cells += [(text, vmerge)] * span
        rows.append(cells)
    matrix = []
    for i, cells in enumerate(rows):
        assert len(cells) == ncols, (docx_path.name, i, len(cells))
        matrix.append([matrix[i - 1][j] if vm == "continue" else txt for j, (txt, vm) in enumerate(cells)])
    return matrix


def verify(docx_path, header, body):
    m = logical_matrix(docx_path, len(header))
    rebuilt = [f"{g}: {s}" if g != s else s for g, s in zip(m[0], m[1])]
    diffs = [(1, header[j], header[j], rebuilt[j]) for j in range(len(header)) if header[j] != rebuilt[j]]
    for i, r in enumerate(body):
        for j, v in enumerate(r):
            if m[2 + i][j] != display_key(v):
                diffs.append((i + 2, header[j], v, m[2 + i][j]))
    return len(body), len(header), len(m) - 2, len(header) * (len(body) + 1), diffs


if __name__ == "__main__":
    notes = {r["file"]: r for r in csv.DictReader((MAIN / "table_titles_notes.csv").open(encoding="utf-8-sig"))}
    total_diff = 0
    for csv_path in sorted(MAIN.glob("Table*.csv")):
        meta = notes[csv_path.stem]
        out, header, body = build(csv_path, meta["title"], meta["note"])
        nrow, ncol, drow, ncmp, diffs = verify(out, header, body)
        total_diff += len(diffs)
        print(f"{out.name}: CSV {nrow}×{ncol}, DOCX {drow}×{ncol}, compared {ncmp} cells, differences {len(diffs)}")
        for d in diffs:
            print("   row", d[0], "|", d[1], "| CSV:", d[2], "| DOCX:", d[3])
    raise SystemExit(1 if total_diff else 0)
