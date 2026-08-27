"""Renders docs/chapters/*.md to docs/FYP_Report.pdf (the full report) and,
optionally, to a standalone PDF per chapter (docs/FYP_Report_ChapterN_*.pdf)
for sharing a single chapter with a supervisor ahead of the full report
being finished. Substitutes the 4 plain-text ASCII diagram sketches for the
proper SVG diagrams from build_diagrams.py along the way (the markdown
source itself is left untouched - ASCII stays there as the editable
version).

The full report is split into two independently-paginated parts, matching
the department's format (preliminary pages numbered i, ii, iii... in
lower-case roman numerals; main work numbered 1, 2, 3... starting at
Chapter One):
- docs/chapters/00_preliminary_pages.md is the preliminary pages
- every other docs/chapters/*.md file, concatenated in filename order, is
  the main work

A standalone chapter PDF has no preliminary pages and is numbered 1, 2,
3... on its own, independent of where that chapter will eventually land in
the full report - it's a review draft, not a fragment of a fixed final
page count.

Each part is printed to its own PDF, then a page-number overlay (roman for
the preliminary pages, arabic for everything else, each restarting at 1) is
stamped on with reportlab/pypdf and the parts are concatenated.

Every numbered sub-section (any h2/h3) is also wrapped so it avoids being
split across a page boundary where it fits on one page; chapters (h1) still
always start a fresh page.

Requires: pip install -r requirements.txt (into a venv is fine), and a
Chromium-based browser on PATH (default: brave-browser).

Usage:
    python3 render_pdf.py                 # full report only (default)
    python3 render_pdf.py --chapters      # full report + one PDF per chapter
    python3 render_pdf.py --chapters-only # one PDF per chapter, skip the full report
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import markdown
from bs4 import BeautifulSoup
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from build_diagrams import FIGURES

HERE = Path(__file__).parent
CHAPTERS_DIR = HERE.parent / 'chapters'
PDF_PATH = HERE.parent / 'FYP_Report.pdf'
BROWSER = 'brave-browser'  # swap for chromium/google-chrome if unavailable

FENCE_RE = re.compile(r'```\n.*?\n```', re.S)
PRE_RE = re.compile(r'<pre><code>.*?</code></pre>', re.S)

BASE_STYLE = '''
body { font-family: "Times New Roman", Georgia, serif; font-size: 12pt; line-height: 1.5; max-width: 7.2in; margin: 0.3in auto; color: #111; }
h1 { font-size: 18pt; page-break-before: always; margin-bottom: 0.2em; text-align: center; }
h1:first-of-type { page-break-before: avoid; }
h1 + h1 { page-break-before: avoid; margin-top: 0.1em; }
h2 { font-size: 14pt; margin-top: 1.2em; }
h3 { font-size: 12.5pt; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10.5pt; }
th, td { border: 1px solid #888; padding: 4px 8px; text-align: left; vertical-align: top; }
pre { background: #f4f4f4; border: 1px solid #ccc; padding: 8px; font-size: 9.5pt; overflow-x: auto; white-space: pre; }
code { font-family: "DejaVu Sans Mono", monospace; }
hr { border: none; border-top: 1px solid #999; margin: 2em 0; }
p { text-align: justify; }
.keep-block { page-break-inside: avoid; break-inside: avoid; }
.title-page, .title-page * { text-align: center; }
'''


def chapter_paths():
    return sorted(p for p in CHAPTERS_DIR.glob('*.md') if not p.name.startswith('00_'))


def prelim_path():
    matches = list(CHAPTERS_DIR.glob('00_*.md'))
    assert len(matches) == 1, f'expected exactly one 00_*.md preliminary-pages file, found {len(matches)}'
    return matches[0]


def figure_offset_for(path):
    offset = 0
    for p in chapter_paths():
        if p == path:
            return offset
        offset += len(FENCE_RE.findall(p.read_text()))
    raise ValueError(f'{path} not found among chapter files')


def to_roman(n):
    vals = [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'),
            (90, 'xc'), (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'),
            (5, 'v'), (4, 'iv'), (1, 'i')]
    out = []
    for val, sym in vals:
        while n >= val:
            out.append(sym)
            n -= val
    return ''.join(out)


def wrap_keep_blocks(html_fragment, max_chars=4000):
    """Group each h2/h3 with the content that follows it (up to the next
    heading) into a .keep-block div, so a sub-section avoids being split
    across a page boundary where it fits on one page. A section too long to
    plausibly fit on a single page (empirically, ~4000 characters of body
    text at this point size) is left unwrapped: page-break-inside: avoid
    on an oversized block just pushes it whole onto the next page and it
    still ends up splitting there, wasting the page it was pushed off of
    for nothing."""
    soup = BeautifulSoup(html_fragment, 'html.parser')
    new_soup = BeautifulSoup('', 'html.parser')
    group_children = None

    def flush():
        if not group_children:
            return
        text_len = sum(len(c.get_text()) if hasattr(c, 'get_text') else len(str(c)) for c in group_children)
        if text_len <= max_chars:
            div = new_soup.new_tag('div')
            div['class'] = 'keep-block'
            new_soup.append(div)
            for c in group_children:
                div.append(c)
        else:
            for c in group_children:
                new_soup.append(c)

    for child in list(soup.contents):
        name = getattr(child, 'name', None)
        if name in ('h2', 'h3'):
            flush()
            group_children = [child.extract()]
        elif name == 'h1':
            flush()
            group_children = None
            new_soup.append(child.extract())
        else:
            if group_children is not None:
                group_children.append(child.extract())
            else:
                new_soup.append(child.extract())
    flush()
    return str(new_soup)


def center_title_page(html_fragment):
    """Wraps the TITLE PAGE heading and everything up to the next h1 in a
    .title-page div, so that page (and only that page) renders centered."""
    soup = BeautifulSoup(html_fragment, 'html.parser')
    children = list(soup.contents)
    out = BeautifulSoup('', 'html.parser')
    i, n = 0, len(children)
    while i < n:
        child = children[i]
        if getattr(child, 'name', None) == 'h1' and child.get_text(strip=True) == 'TITLE PAGE':
            out.append(child.extract())
            block = out.new_tag('div')
            block['class'] = 'title-page'
            out.append(block)
            i += 1
            while i < n and getattr(children[i], 'name', None) != 'h1':
                block.append(children[i].extract())
                i += 1
            continue
        out.append(child.extract())
        i += 1
    return str(out)


def substitute_figures(body_html, figures_slice):
    matches = list(PRE_RE.finditer(body_html))
    assert len(matches) == len(figures_slice), f'expected {len(figures_slice)} pre blocks, found {len(matches)}'
    new_body = []
    last_end = 0
    for m, svg_html in zip(matches, figures_slice):
        new_body.append(body_html[last_end:m.start()])
        new_body.append(svg_html)
        last_end = m.end()
    new_body.append(body_html[last_end:])
    return ''.join(new_body)


def make_html(body_html):
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{BASE_STYLE}</style></head><body>{body_html}</body></html>'''


def print_html(html_path, pdf_path):
    subprocess.run([sys.executable, str(HERE / 'print_pdf.py'), str(html_path), str(pdf_path)], check=True)


def numbering_overlay(overlay_path, count, style):
    c = canvas.Canvas(str(overlay_path), pagesize=letter)
    for i in range(1, count + 1):
        label = to_roman(i) if style == 'roman' else str(i)
        c.setFont('Times-Roman', 11)
        c.drawCentredString(letter[0] / 2, 28, label)
        c.showPage()
    c.save()


def numbered_writer(pdf_path, style):
    reader = PdfReader(str(pdf_path))
    overlay_path = pdf_path.with_suffix('.numbers.pdf')
    numbering_overlay(overlay_path, len(reader.pages), style)
    overlay_reader = PdfReader(str(overlay_path))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        page.merge_page(overlay_reader.pages[i])
        writer.add_page(page)
    overlay_path.unlink()
    return writer


def render(body_src, figures_slice, pdf_path, prelim_src=None, tag='render'):
    """Assumes a headless browser is already running (see main())."""
    body_html = markdown.markdown(body_src, extensions=['tables', 'fenced_code'])
    body_html = wrap_keep_blocks(body_html)
    body_html = substitute_figures(body_html, figures_slice)

    body_html_path = HERE / f'_{tag}_body.html'
    body_pdf_path = HERE / f'_{tag}_body.pdf'
    body_html_path.write_text(make_html(body_html))
    to_cleanup = [body_html_path, body_pdf_path]

    prelim_html_path = prelim_pdf_path = None
    if prelim_src is not None:
        prelim_html = markdown.markdown(prelim_src, extensions=['tables', 'fenced_code'])
        prelim_html = center_title_page(prelim_html)
        prelim_html_path = HERE / f'_{tag}_prelim.html'
        prelim_pdf_path = HERE / f'_{tag}_prelim.pdf'
        prelim_html_path.write_text(make_html(prelim_html))
        to_cleanup += [prelim_html_path, prelim_pdf_path]

    if prelim_html_path:
        print_html(prelim_html_path, prelim_pdf_path)
    print_html(body_html_path, body_pdf_path)

    body_writer = numbered_writer(body_pdf_path, 'arabic')
    final_writer = PdfWriter()
    prelim_count = 0
    if prelim_pdf_path:
        prelim_writer = numbered_writer(prelim_pdf_path, 'roman')
        prelim_count = len(prelim_writer.pages)
        for page in prelim_writer.pages:
            final_writer.add_page(page)
    for page in body_writer.pages:
        final_writer.add_page(page)

    with open(pdf_path, 'wb') as f:
        final_writer.write(f)
    for p in to_cleanup:
        p.unlink()

    if prelim_count:
        print('wrote', pdf_path, f'({prelim_count} preliminary + {len(body_writer.pages)} main pages)')
    else:
        print('wrote', pdf_path, f'({len(body_writer.pages)} pages)')


def render_full():
    body_src = '\n\n---\n\n'.join(p.read_text() for p in chapter_paths())
    render(body_src, FIGURES, PDF_PATH, prelim_src=prelim_path().read_text(), tag='full')


def render_chapter(path):
    body_src = path.read_text()
    offset = figure_offset_for(path)
    n = len(FENCE_RE.findall(body_src))
    figures_slice = FIGURES[offset:offset + n]
    label = path.stem.split('_', 1)[1]  # e.g. 'chapter_one_introduction'
    out_path = HERE.parent / f'FYP_Report_{label}.pdf'
    render(body_src, figures_slice, out_path, tag=label)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chapters', action='store_true', help='also build a standalone PDF per chapter')
    parser.add_argument('--chapters-only', action='store_true', help='build only the standalone chapter PDFs, skip the full report')
    args = parser.parse_args()

    subprocess.Popen(
        [BROWSER, '--headless=new', '--disable-gpu', '--no-sandbox',
         '--remote-debugging-port=9333', '--remote-allow-origins=*', 'about:blank'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2)
    try:
        if not args.chapters_only:
            render_full()
        if args.chapters or args.chapters_only:
            for p in chapter_paths():
                render_chapter(p)
    finally:
        subprocess.run(['pkill', '-f', 'remote-debugging-port=9333'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
