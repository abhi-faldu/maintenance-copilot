"""Render Markdown to a manual-style PDF with PyMuPDF's Story API.

Used to build the synthetic corpus (tools/build_manuals.py) and to create small PDF
fixtures in tests. The output deliberately looks like a real manual: running header and
footer on every page, ruled tables that may break across pages, numbered headings.
The parser never sees the Markdown, only the PDF.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf

PAGE = pymupdf.paper_rect("a4")
MARGIN_X = 56
MARGIN_TOP = 64
MARGIN_BOTTOM = 64
CONTENT = PAGE + (MARGIN_X, MARGIN_TOP, -MARGIN_X, -MARGIN_BOTTOM)

CSS = """
* { font-family: sans-serif; }
body { font-size: 10pt; line-height: 1.3; }
h1 { font-size: 18pt; font-weight: bold; margin: 0 0 10pt 0; }
h2 { font-size: 14pt; font-weight: bold; margin: 14pt 0 6pt 0; }
h3 { font-size: 12pt; font-weight: bold; margin: 12pt 0 4pt 0; }
h4 { font-size: 11pt; font-weight: bold; margin: 10pt 0 4pt 0; }
p  { margin: 0 0 6pt 0; }
li { margin: 0 0 2pt 0; }
table { border-collapse: separate; border-spacing: 0; margin: 4pt 0 10pt 0; width: 100%; }
th, td { border: 0.6pt solid #444; padding: 2pt 4pt; font-size: 9pt; text-align: left;
         vertical-align: top; }
th { font-weight: bold; }
.cover { font-size: 26pt; font-weight: bold; margin: 160pt 0 12pt 0; }
.cover-sub { font-size: 13pt; margin: 0 0 6pt 0; }
"""

PAGE_BREAK = "<!-- pagebreak -->"


def markdown_to_html(md_text: str) -> str:
    import markdown  # dev dependency; only needed to build PDFs

    parts = md_text.split(PAGE_BREAK)
    html_parts = [markdown.markdown(p, extensions=["tables", "sane_lists"]) for p in parts]
    # Story honours page-break-before on block elements.
    return '<div style="page-break-before: always"></div>'.join(html_parts)


def render_pdf(
    md_text: str,
    out_path: str | Path,
    *,
    title: str,
    header: str,
    footer_id: str,
    lang: str = "en",
) -> Path:
    """Render Markdown to a PDF with running header/footer. Returns the output path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = markdown_to_html(md_text)
    story = pymupdf.Story(html=html, user_css=CSS)

    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    more = True
    while more:
        dev = writer.begin_page(PAGE)
        more, _ = story.place(CONTENT)
        story.draw(dev)
        writer.end_page()
    writer.close()

    tmp = pymupdf.open("pdf", buf.getvalue())
    n = tmp.page_count
    for i, page in enumerate(tmp, start=1):
        if i == 1:
            continue  # cover page has no running header/footer
        page.insert_text((MARGIN_X, 36), header, fontsize=8, fontname="helv")
        page.draw_line((MARGIN_X, 42), (PAGE.width - MARGIN_X, 42), width=0.5)
        page.draw_line(
            (MARGIN_X, PAGE.height - 44), (PAGE.width - MARGIN_X, PAGE.height - 44), width=0.5
        )
        page.insert_text((MARGIN_X, PAGE.height - 32), f"{footer_id}", fontsize=8, fontname="helv")
        page.insert_text(
            (PAGE.width - MARGIN_X - 60, PAGE.height - 32),
            f"Page {i} of {n}",
            fontsize=8,
            fontname="helv",
        )
    tmp.set_metadata(
        {
            "title": title,
            "subject": f"lang={lang}",
            "author": "Synthetic corpus (maintenance-copilot)",
            "producer": "PyMuPDF Story",
        }
    )
    tmp.save(out_path, garbage=3, deflate=True)
    tmp.close()
    return out_path
