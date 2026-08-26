"""Builds proper SVG diagrams to replace the 4 ASCII-sketch <pre> blocks
when rendering the PDF/DOCX. The markdown source keeps the ASCII as-is."""

ARROW_DEFS = '''<defs>
  <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6 Z" fill="#333"/>
  </marker>
</defs>'''

BOX_STYLE = 'fill="#f7f7f7" stroke="#444" stroke-width="1.3" rx="6"'
TEXT_STYLE = 'font-family="Georgia, serif" font-size="13" fill="#111" text-anchor="middle"'
LABEL_STYLE = 'font-family="Georgia, serif" font-size="11.5" fill="#333" text-anchor="middle"'
STEP_STYLE = 'font-family="Georgia, serif" font-size="11" fill="#555"'


def wrap(inner, w, h, caption=None):
    svg = f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" xmlns="http://www.w3.org/2000/svg">{ARROW_DEFS}{inner}</svg>'
    div = f'<div style="text-align:center; margin: 0.6em 0; padding: 10px; background:#fafafa; border:1px solid #ddd;">{svg}</div>'
    return div


def multiline_text(cx, cy, lines, style=TEXT_STYLE, line_height=15):
    n = len(lines)
    start_y = cy - (n - 1) * line_height / 2
    out = ''
    for i, line in enumerate(lines):
        y = start_y + i * line_height
        out += f'<text x="{cx}" y="{y}" {style}>{line}</text>'
    return out


def box(cx, cy, w, h, lines):
    x, y = cx - w / 2, cy - h / 2
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {BOX_STYLE}/>'
    out += multiline_text(cx, cy, lines)
    return out


def h_arrow(x1, x2, y, label=None, dy_label=-6):
    out = f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#333" stroke-width="1.4" marker-end="url(#arrow)"/>'
    if label:
        cx = (x1 + x2) / 2
        out += f'<text x="{cx}" y="{y + dy_label}" {LABEL_STYLE}>{label}</text>'
    return out


def v_arrow(x, y1, y2, label=None, dx_label=8, anchor='start'):
    out = f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#333" stroke-width="1.4" marker-end="url(#arrow)"/>'
    if label:
        cy = (y1 + y2) / 2
        style = LABEL_STYLE.replace('text-anchor="middle"', f'text-anchor="{anchor}"')
        out += f'<text x="{x + dx_label}" y="{cy}" {style}>{label}</text>'
    return out


def lifeline(x, y_top, y_bottom):
    return f'<line x1="{x}" y1="{y_top}" x2="{x}" y2="{y_bottom}" stroke="#999" stroke-width="1" stroke-dasharray="4,3"/>'


def self_note(x, y, lines):
    """Centered, small multi-line note for a self-directed step (no line crossing columns)."""
    out = f'<rect x="{x - 105}" y="{y - 20}" width="210" height="{16 * len(lines) + 10}" fill="#fff" stroke="#bbb" stroke-width="0.8" rx="4"/>'
    out += multiline_text(x, y, lines, style=STEP_STYLE.replace('fill="#555"', 'fill="#555" text-anchor="middle"'), line_height=15)
    return out


# ---------------------------------------------------------------
# Figure 2.1: Basic System Components
# ---------------------------------------------------------------
def figure_2_1():
    w, h = 700, 190
    y = 90
    b1, b2, b3 = 130, 350, 570
    inner = ''
    inner += box(b1, y, 170, 90, ['People', '(students, staff)'])
    inner += box(b2, y, 170, 90, ['Process', '(registration,', 'results, records)'])
    inner += box(b3, y, 170, 90, ['Technology', '(this portal:', 'Django app, database)'])
    inner += h_arrow(b1 + 85, b2 - 85, y - 14)
    inner += h_arrow(b2 - 85, b1 + 85, y + 24, )
    inner += h_arrow(b2 + 85, b3 - 85, y - 14)
    inner += h_arrow(b3 - 85, b2 + 85, y + 24)
    return wrap(inner, w, h)


# ---------------------------------------------------------------
# Figure 3.1: Dataflow of the Existing (Manual) System
# ---------------------------------------------------------------
def figure_3_1():
    w, h = 780, 460
    x1, x2, x3 = 110, 400, 640
    top = 40
    bottom = 430
    inner = ''
    inner += box(x1, top, 170, 46, ['Student'])
    inner += box(x2, top, 200, 46, ["Registrar's Office"])
    inner += box(x3, top, 190, 46, ['Lecturer / HOD'])
    inner += lifeline(x1, top + 23, bottom)
    inner += lifeline(x2, top + 23, bottom)
    inner += lifeline(x3, top + 23, bottom)

    y = 95
    inner += h_arrow(x1, x2, y, '1. Submits paper registration form')
    y += 55
    inner += self_note(x2, y, ['2. Manually records on', 'spreadsheet/ledger'])
    y += 55
    inner += h_arrow(x2, x3, y, '3. Compiles class list for each course')
    y += 55
    inner += self_note(x3, y, ['4. Teaches, sets/marks', 'exams manually'])
    y += 55
    inner += h_arrow(x3, x2, y, '5. Hands back scores on paper/spreadsheet')
    y += 55
    inner += h_arrow(x1, x2, y, '6. Asks staff in person / waits for notice')
    y += 40
    inner += h_arrow(x2, x1, y, 'Finds out result')
    return wrap(inner, w, h)


# ---------------------------------------------------------------
# Figure 3.2: Dataflow Diagram of the Web-Based (Proposed) System
# ---------------------------------------------------------------
def figure_3_2():
    w, h = 780, 560
    x1, x2, x3 = 110, 400, 640
    top = 40
    bottom = 530
    inner = ''
    inner += box(x1, top, 170, 46, ['Student'])
    inner += box(x2, top, 230, 46, ['Portal (RBAC-checked)'])
    inner += box(x3, top, 190, 46, ['Lecturer / HOD'])
    inner += lifeline(x1, top + 23, bottom)
    inner += lifeline(x2, top + 23, bottom)
    inner += lifeline(x3, top + 23, bottom)

    y = 95
    inner += h_arrow(x1, x2, y, '1. Logs in')
    y += 55
    inner += self_note(x2, y, ['2. Role decorator verifies', 'Student role, grants access'])
    y += 55
    inner += h_arrow(x1, x2, y, '3. Registers for course')
    y += 55
    inner += self_note(x2, y, ['4. Writes CourseRegistration', 'row, scoped to that student'])
    y += 55
    inner += h_arrow(x2, x3, y, '5. Course list, scoped to assigned courses')
    y += 55
    inner += self_note(x3, y, ['6. Enters scores via', 'ScoreEntryForm'])
    y += 55
    inner += h_arrow(x3, x2, y, '7. Result graded automatically (NUC scale), stored')
    y += 45
    inner += h_arrow(x2, x1, y, '8-9. Views result/GPA directly, no request needed')
    return wrap(inner, w, h)


# ---------------------------------------------------------------
# Figure 4.1: High Level Model of the New System
# ---------------------------------------------------------------
def figure_4_1():
    w, h = 560, 640
    cx = 280
    inner = ''
    y = 40
    inner += box(cx, y, 280, 50, ['Web Browser', '(Student / Staff)'])

    outer_top = y + 55
    outer_bottom = outer_top + 400
    inner += f'<rect x="{cx - 240}" y="{outer_top}" width="480" height="{outer_bottom - outer_top}" fill="#fff" stroke="#666" stroke-width="1.4" rx="8" stroke-dasharray="0"/>'
    inner += f'<text x="{cx}" y="{outer_top + 22}" {LABEL_STYLE} font-style="italic">Django Application (lu_sims project)</text>'

    inner += v_arrow(cx, y + 25, outer_top + 5, 'HTTP(S)', dx_label=10)

    step_y = outer_top + 55
    step_h = 46
    gap = 22
    steps = [
        'URL Dispatcher -&gt; Auth Middleware',
        'Role Decorator (@&lt;role&gt;_required)',
        'View',
        'Template (Bootstrap 5)',
    ]
    ys = []
    for label in steps:
        inner += box(cx, step_y, 380, step_h, [label])
        ys.append(step_y)
        step_y += step_h + gap
    for i in range(len(ys) - 1):
        inner += v_arrow(cx, ys[i] + step_h / 2, ys[i + 1] - step_h / 2)

    orm_y = step_y
    inner += box(cx, orm_y, 380, 46, ['Django ORM'])
    inner += v_arrow(cx, ys[-1] + step_h / 2, orm_y - 23)

    db_y = outer_bottom + 60
    inner += v_arrow(cx, orm_y + 23, db_y - 30)
    inner += box(cx, db_y, 220, 60, ['SQLite', 'db.sqlite3'])

    return wrap(inner, w, h)


FIGURES = [figure_2_1(), figure_3_1(), figure_3_2(), figure_4_1()]
