# Report render pipeline

Regenerates `docs/FYP_Report.pdf` and `docs/FYP_Report.docx` from the
markdown source in `docs/chapters/` after an edit. Each chapter is its own
file there (`00_preliminary_pages.md`, `01_chapter_one_introduction.md`,
`02_chapter_two_literature_review.md`, `03_chapter_three_methodology.md`,
more to follow as later chapters get written) — numeric prefixes control
assembly order, and there's no combined `FYP_Report.md` anymore; the build
scripts concatenate the chapter files in memory. Splitting a chapter out
onto its own file this way is also what lets it be built as a standalone
PDF/DOCX (see `--chapters` below) for review, e.g. sharing one chapter at a
time with a supervisor before the full report is finished. The markdown
keeps the 4 diagrams as plain ASCII sketches (editable, no tooling needed);
both rendered outputs get proper redrawn diagrams substituted in instead.

The full report follows the department format: preliminary pages (Title
through Abstract, `00_preliminary_pages.md`) are numbered i, ii, iii... and
the main work restarts at 1, 2, 3... from Chapter One. A standalone chapter
build has no preliminary pages and is numbered 1, 2, 3... on its own —
independent of where that chapter will eventually land in the full report,
since it's a review draft, not a fragment of a fixed final page count. In
both cases, each chapter/preliminary page starts on its own page, and a
numbered sub-section (h2/h3) is kept off a page split where it's short
enough to plausibly fit on one page (long sections are left to flow and
split naturally rather than being pushed onto a fresh page and wasting the
one they left mostly blank). Table of Contents / List of Tables / List of
Figures are intentionally not generated yet — they need final page numbers
that only make sense once Chapters Four and Five, References, and the
Appendices exist.

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
.venv/bin/python3 render_pdf.py         # -> ../FYP_Report.pdf (full report only)
.venv/bin/python3 gen_figure_pngs.py    # -> fig_2_1.png etc. (needed by build_docx.py)
.venv/bin/python3 build_docx.py         # -> ../FYP_Report.docx (full report only)
```

Add `--chapters` to also build a standalone PDF/DOCX per chapter
(`../FYP_Report_chapter_one_introduction.pdf`, etc.), or `--chapters-only`
to build just those and skip the full report.

`build_diagrams.py` holds the actual diagram content (SVG, as Python
functions) — edit there if a diagram itself needs to change, not in the
generated HTML/PNGs. `print_pdf.py` is a small DevTools-protocol helper
`render_pdf.py` calls; not meant to be run standalone.

The generated `fig_*.png`/`fig_*.html` files in this directory are
build artifacts (gitignored) — safe to delete, `gen_figure_pngs.py`
regenerates them.
