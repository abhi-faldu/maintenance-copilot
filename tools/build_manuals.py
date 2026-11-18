"""Render the synthetic manuals in corpus/src/*.md to corpus/manuals/*.pdf.

Usage: uv run python tools/build_manuals.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ingest.pdf_render import render_pdf  # noqa: E402

MANUALS = {
    "RA-3_Service_Manual_EN": {
        "title": "RA-3 Operating and Service Manual",
        "header": "RA-3 Six-Axis Articulated Robot | Operating and Service Manual",
        "footer_id": "RA3-SM-EN Rev. 1.0",
        "lang": "en",
    },
}


def main() -> None:
    src_dir = ROOT / "corpus" / "src"
    out_dir = ROOT / "corpus" / "manuals"
    for stem, meta in MANUALS.items():
        md = (src_dir / f"{stem}.md").read_text(encoding="utf-8")
        out = render_pdf(md, out_dir / f"{stem}.pdf", **meta)
        import pymupdf

        with pymupdf.open(out) as doc:
            print(f"{out.relative_to(ROOT)}: {doc.page_count} pages")


if __name__ == "__main__":
    main()
