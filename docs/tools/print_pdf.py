"""Prints a local HTML file to PDF via a headless Chromium-based browser's
DevTools protocol (Page.printToPDF), with no browser header/footer and no
CLI-flag flakiness. Used by render_pdf.py.

Usage: python3 print_pdf.py <html_path> <pdf_out_path>
Assumes a headless browser is already running with
--remote-debugging-port=9333 --remote-allow-origins=* (see render_pdf.py).
"""
import base64
import json
import sys

import requests
import websocket

html_path = sys.argv[1]
out_path = sys.argv[2]
port = 9333

r = requests.put(f"http://localhost:{port}/json/new?about:blank")
tab = r.json()
tab_id = tab["id"]
ws_url = tab["webSocketDebuggerUrl"]

ws = websocket.create_connection(ws_url)


def send(method, params=None, msg_id=1):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            return resp


send("Page.enable", msg_id=1)
send("Page.navigate", {"url": f"file://{html_path}"}, msg_id=2)

while True:
    resp = json.loads(ws.recv())
    if resp.get("method") == "Page.loadEventFired":
        break

result = send("Page.printToPDF", {
    "printBackground": True,
    "displayHeaderFooter": False,
    "preferCSSPageSize": False,
    "marginTop": 0.6,
    "marginBottom": 0.6,
    "marginLeft": 0.7,
    "marginRight": 0.7,
}, msg_id=3)

pdf_data = result["result"]["data"]
with open(out_path, "wb") as f:
    f.write(base64.b64decode(pdf_data))

ws.close()
requests.get(f"http://localhost:{port}/json/close/{tab_id}")
print("wrote", out_path)
