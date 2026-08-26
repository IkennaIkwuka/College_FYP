# Report render pipeline

Regenerates `docs/FYP_Report.pdf` and `docs/FYP_Report.docx` from
`docs/FYP_Report.md` after an edit. The markdown keeps the 4 diagrams as
plain ASCII sketches (editable, no tooling needed); both rendered outputs
get proper redrawn diagrams substituted in instead.

## Setup (once)

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Also needs a Chromium-based browser on PATH — defaults to `brave-browser`
(edit the `BROWSER` constant in `gen_figure_pngs.py` / `render_pdf.py` if
using `chromium` or `google-chrome` instead).

## Regenerate

```
.venv/bin/python3 render_pdf.py         # -> ../FYP_Report.pdf
.venv/bin/python3 gen_figure_pngs.py    # -> fig_2_1.png etc. (needed by build_docx.py)
.venv/bin/python3 build_docx.py         # -> ../FYP_Report.docx
```

`build_diagrams.py` holds the actual diagram content (SVG, as Python
functions) — edit there if a diagram itself needs to change, not in the
generated HTML/PNGs. `print_pdf.py` is a small DevTools-protocol helper
`render_pdf.py` calls; not meant to be run standalone.

The generated `fig_*.png`/`fig_*.html` files in this directory are
build artifacts (gitignored) — safe to delete, `gen_figure_pngs.py`
regenerates them.
