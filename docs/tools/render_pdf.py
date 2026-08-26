"""Renders docs/FYP_Report.md to docs/FYP_Report.pdf, substituting the 4
plain-text ASCII sketches for the proper SVG diagrams from build_diagrams.py
(the markdown source itself is left untouched - ASCII stays there as the
editable version).

Requires: pip install markdown requests websocket-client (into a venv is
fine), and a Chromium-based browser on PATH (default: brave-browser).

Usage: python3 render_pdf.py
"""
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import markdown
from build_diagrams import FIGURES

HERE = Path(__file__).parent
MD_PATH = HERE.parent / 'FYP_Report.md'
HTML_PATH = HERE / '_FYP_Report_render.html'
PDF_PATH = HERE.parent / 'FYP_Report.pdf'
BROWSER = 'brave-browser'  # swap for chromium/google-chrome if unavailable

src = MD_PATH.read_text()
body = markdown.markdown(src, extensions=['tables', 'fenced_code'])

pre_pattern = re.compile(r'<pre><code>.*?</code></pre>', re.S)
matches = list(pre_pattern.finditer(body))
assert len(matches) == len(FIGURES), f'expected {len(FIGURES)} pre blocks, found {len(matches)}'

new_body = []
last_end = 0
for m, svg_html in zip(matches, FIGURES):
    new_body.append(body[last_end:m.start()])
    new_body.append(svg_html)
    last_end = m.end()
new_body.append(body[last_end:])
body = ''.join(new_body)

html = '''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body { font-family: "Times New Roman", Georgia, serif; font-size: 12pt; line-height: 1.5; max-width: 7.2in; margin: 0.3in auto; color: #111; }
h1 { font-size: 18pt; page-break-before: always; margin-bottom: 0.2em; }
h1:first-of-type { page-break-before: avoid; }
h1 + h1 { page-break-before: avoid; margin-top: 0.1em; }
h2 { font-size: 14pt; margin-top: 1.2em; }
h3 { font-size: 12.5pt; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10.5pt; }
th, td { border: 1px solid #888; padding: 4px 8px; text-align: left; vertical-align: top; }
pre { background: #f4f4f4; border: 1px solid #ccc; padding: 8px; font-size: 9.5pt; overflow-x: auto; white-space: pre; }
code { font-family: "DejaVu Sans Mono", monospace; }
hr { border: none; border-top: 1px solid #999; margin: 2em 0; }
</style></head><body>''' + body + '</body></html>'

HTML_PATH.write_text(html)

subprocess.Popen(
    [BROWSER, '--headless=new', '--disable-gpu', '--no-sandbox',
     '--remote-debugging-port=9333', '--remote-allow-origins=*', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(2)

subprocess.run([sys.executable, str(HERE / 'print_pdf.py'), str(HTML_PATH), str(PDF_PATH)], check=True)

subprocess.run(['pkill', '-f', 'remote-debugging-port=9333'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
HTML_PATH.unlink()
print('wrote', PDF_PATH)
