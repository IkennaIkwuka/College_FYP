"""Renders the 4 SVG diagrams from build_diagrams.py to standalone PNG files,
via a headless Chromium-based browser (brave-browser by default) over the
DevTools protocol. Run this before build_docx.py, and before regenerating
the PDF if any diagram content changed.

Usage: python3 gen_figure_pngs.py
Output: fig_2_1.png, fig_3_1.png, fig_3_2.png, fig_4_1.png, written next to
this script.
"""
import base64
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import requests
import websocket
from build_diagrams import FIGURES

HERE = Path(__file__).parent
PORT = 9334
NAMES = ['fig_2_1', 'fig_3_1', 'fig_3_2', 'fig_4_1']
BROWSER = 'brave-browser'  # swap for chromium/google-chrome if unavailable

proc = subprocess.Popen(
    [BROWSER, '--headless=new', '--disable-gpu', '--no-sandbox',
     f'--remote-debugging-port={PORT}', '--remote-allow-origins=*', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
time.sleep(2)

for name, html_fragment in zip(NAMES, FIGURES):
    svg_match = re.search(r'<svg.*?</svg>', html_fragment, re.S)
    svg_only = svg_match.group(0)
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg_only)
    w, h = int(m.group(1)), int(m.group(2))
    pad = 10
    full_w, full_h = w + pad * 2, h + pad * 2

    html_path = HERE / f'{name}.html'
    html_path.write_text(f'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
html, body {{ margin:0; padding:0; overflow:hidden; width:{full_w}px; height:{full_h}px; background:#fff; }}
.box {{ padding:{pad}px; background:#fafafa; box-sizing:border-box; width:{full_w}px; height:{full_h}px; }}
svg {{ display:block; }}
</style></head><body><div class="box">{svg_only}</div></body></html>''')

    r = requests.put(f'http://localhost:{PORT}/json/new?about:blank')
    tab = r.json()
    tab_id = tab['id']
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'])

    def send(method, params=None, msg_id=1):
        ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get('id') == msg_id:
                return resp

    send('Page.enable', msg_id=1)
    send('Emulation.setDeviceMetricsOverride', {
        'width': full_w, 'height': full_h, 'deviceScaleFactor': 3, 'mobile': False,
    }, msg_id=2)
    send('Page.navigate', {'url': f'file://{html_path}'}, msg_id=3)
    while True:
        resp = json.loads(ws.recv())
        if resp.get('method') == 'Page.loadEventFired':
            break
    time.sleep(0.3)
    result = send('Page.captureScreenshot', {
        'format': 'png',
        'clip': {'x': 0, 'y': 0, 'width': full_w, 'height': full_h, 'scale': 1},
    }, msg_id=4)
    png_data = result['result']['data']
    (HERE / f'{name}.png').write_bytes(base64.b64decode(png_data))
    ws.close()
    requests.get(f'http://localhost:{PORT}/json/close/{tab_id}')
    html_path.unlink()
    print('wrote', HERE / f'{name}.png', full_w, full_h)

subprocess.run(['pkill', '-f', f'remote-debugging-port={PORT}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
