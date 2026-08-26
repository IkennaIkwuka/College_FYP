"""Renders docs/FYP_Report.md to docs/FYP_Report.docx via pandoc
(pypandoc_binary), substituting the 4 ASCII sketches for the diagram PNGs
(run gen_figure_pngs.py first), then post-processes with python-docx to:
force each chapter onto its own page, keep every heading glued to the
content right after it, and keep tables from splitting across a page
boundary.

Requires: pip install pypandoc_binary python-docx (into a venv is fine).

Usage: python3 gen_figure_pngs.py && python3 build_docx.py
"""
import re
from pathlib import Path

import pypandoc
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor

HERE = Path(__file__).parent
MD_PATH = HERE.parent / 'FYP_Report.md'
TEMP_MD = HERE / '_FYP_Report_for_docx.md'
DOCX_PATH = HERE.parent / 'FYP_Report.docx'

PNGS = [HERE / 'fig_2_1.png', HERE / 'fig_3_1.png', HERE / 'fig_3_2.png', HERE / 'fig_4_1.png']
for p in PNGS:
    assert p.exists(), f'{p} missing - run gen_figure_pngs.py first'

src = MD_PATH.read_text()

code_block_re = re.compile(r'```\n.*?\n```', re.S)
idx = 0


def replace_block(m):
    global idx
    png = PNGS[idx]
    idx += 1
    return f'![]({png})'


new_src = code_block_re.sub(replace_block, src)
assert idx == 4, f'expected 4 code blocks, replaced {idx}'

TEMP_MD.write_text(new_src)

pypandoc.convert_file(str(TEMP_MD), 'docx', outputfile=str(DOCX_PATH), extra_args=['--standalone'])
TEMP_MD.unlink()

# ---- post-process with python-docx ----
doc = Document(str(DOCX_PATH))

normal = doc.styles['Normal']
normal.font.name = 'Times New Roman'
normal.font.size = Pt(12)

for level, size in [(1, 16), (2, 13), (3, 12)]:
    try:
        style = doc.styles[f'Heading {level}']
        style.font.name = 'Times New Roman'
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
    except KeyError:
        pass


def add_grid_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '888888')
        borders.append(el)
    tblPr.append(borders)


def prevent_row_split(table):
    for row in table.rows:
        trPr = row._tr.get_or_add_trPr()
        cant_split = OxmlElement('w:cantSplit')
        trPr.append(cant_split)


paras = doc.paragraphs
prev_style = None
first_heading_seen = False

for p in paras:
    style_name = p.style.name if p.style else ''
    is_heading = style_name.startswith('Heading')
    if is_heading:
        p.paragraph_format.keep_with_next = True
        if style_name == 'Heading 1':
            if not first_heading_seen:
                first_heading_seen = True
            elif prev_style == 'Heading 1':
                pass
            else:
                p.paragraph_format.page_break_before = True
    if p.runs and p.runs[0].bold and p.text.strip().startswith('Figure '):
        p.paragraph_format.keep_with_next = True
    prev_style = style_name

for table in doc.tables:
    add_grid_borders(table)
    prevent_row_split(table)
    n_rows = len(table.rows)
    for i, row in enumerate(table.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_together = True
                if i < n_rows - 1:
                    p.paragraph_format.keep_with_next = True

doc.save(str(DOCX_PATH))
print('wrote', DOCX_PATH)
