from __future__ import annotations

from pathlib import Path

import pytest

from ingest.parser import parse_pdf
from ingest.pdf_render import render_pdf

ROOT = Path(__file__).resolve().parents[1]
RA3_PDF = ROOT / "corpus" / "manuals" / "RA-3_Service_Manual_EN.pdf"


@pytest.fixture
def make_pdf(tmp_path):
    """Render Markdown to a manual-style PDF (running header/footer, ruled tables)."""

    def _make(md: str, name: str = "Test_Manual_EN.pdf") -> Path:
        return render_pdf(
            md, tmp_path / name, title="Test Manual", header="ACME Test Manual", footer_id="TM-01"
        )

    return _make


@pytest.fixture(scope="session")
def ra3_doc():
    if not RA3_PDF.exists():
        pytest.skip("corpus PDF missing: run `uv run python tools/build_manuals.py`")
    return parse_pdf(RA3_PDF)
