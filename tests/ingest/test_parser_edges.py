"""Regression tests for parser edge cases found in the week-1 review."""

from __future__ import annotations

import pymupdf

from ingest.parser import parse_pdf


def _table(start: int, n: int, header: str = "| Code | Description |") -> str:
    rows = "\n".join(f"| E-{start + i} | Fault {start + i} |" for i in range(n))
    return f"{header}\n|---|---|\n{rows}\n"


# Running headers/footers are only learned from documents with >= 3 pages.
# Body text must outweigh heading text, or the parser cannot tell which size is "body".
FILLER = "This page carries enough ordinary body text to set the body font size. " * 3
TAIL = (
    f"\n\n<!-- pagebreak -->\n\n# 2 Tail\n\n{FILLER}\n\n<!-- pagebreak -->\n\n# 3 End\n\n{FILLER}\n"
)


def _blocks(doc, sid: str):
    return next(s for s in doc.sections if s.section_id == sid).blocks


def test_continuation_with_repeated_header_is_stitched(make_pdf):
    md = f"# 1 Codes\n\n{_table(100, 5)}\n<!-- pagebreak -->\n\n{_table(105, 5)}{TAIL}"
    tables = [b for b in _blocks(parse_pdf(make_pdf(md)), "1") if b.kind == "table"]

    assert len(tables) == 1
    t = tables[0]
    assert (t.page_start, t.page_end) == (1, 2)
    assert t.rows[0] == ["Code", "Description"]
    assert [r[0] for r in t.rows[1:]] == [f"E-{i}" for i in range(100, 110)]  # header not repeated


def test_table_with_a_different_header_is_not_stitched(make_pdf):
    other = _table(105, 5, header="| Part | Name |")
    md = f"# 1 Codes\n\n{_table(100, 5)}\n<!-- pagebreak -->\n\n{other}{TAIL}"
    tables = [b for b in _blocks(parse_pdf(make_pdf(md)), "1") if b.kind == "table"]
    assert len(tables) == 2


def test_body_text_equal_to_running_header_is_kept(make_pdf):
    pages = [
        f"# {i} Chapter\n\nIntro {i}.\n\nACME Test Manual\n\nMore text {i}." for i in range(1, 5)
    ]
    doc = parse_pdf(make_pdf("\n\n<!-- pagebreak -->\n\n".join(pages)))
    texts = [b.text for s in doc.sections for b in s.blocks]

    assert texts.count("ACME Test Manual") == 4  # same text as the header, but in the body
    assert not any("TM-01" in t or "Page " in t for t in texts)  # real header/footer gone


def test_text_beside_a_table_is_kept(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    xs, ys = (50, 150, 250), (100, 120, 140, 160)
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[-1]))
    for y in ys:
        page.draw_line((xs[0], y), (xs[-1], y))
    for r, y in enumerate(ys[:-1]):
        page.insert_text((55, y + 14), f"R{r}A", fontsize=10)
        page.insert_text((155, y + 14), f"R{r}B", fontsize=10)
    page.insert_text((320, 134), "WARNING beside the table.", fontsize=10)
    path = tmp_path / "side_EN.pdf"
    doc.save(path)

    parsed = parse_pdf(path)
    blocks = [b for s in parsed.sections for b in s.blocks]
    assert any(b.kind == "table" and b.rows[0] == ["R0A", "R0B"] for b in blocks)
    assert any(b.kind == "text" and "WARNING beside the table." in b.text for b in blocks)


def test_caption_at_page_foot_is_not_glued_to_next_page(make_pdf):
    page_2 = "The next page starts here."
    md = f"# 1 Gearbox\n\nFigure 4 J3 gearbox\n\n<!-- pagebreak -->\n\n{page_2}{TAIL}"
    texts = [b.text for b in _blocks(parse_pdf(make_pdf(md)), "1")]
    assert texts == ["Figure 4 J3 gearbox", "The next page starts here."]


def test_ra3_sentence_continuing_with_a_digit_is_rejoined(ra3_doc):
    # §8.3 breaks "...compare the" / "7-day average..." across pages 15-16.
    blocks = next(s for s in ra3_doc.sections if s.section_id == "8.3").blocks
    joined = next(b for b in blocks if "compare the 7-day average" in b.text)
    assert (joined.page_start, joined.page_end) == (15, 16)


def test_sentence_broken_by_page_break_is_rejoined(make_pdf):
    para = "the arm moves and the gearbox warms up " * 450
    blocks = _blocks(parse_pdf(make_pdf(f"# 1 Long\n\n{para.strip()}")), "1")
    assert len(blocks) == 1
    assert blocks[0].page_end > blocks[0].page_start
    assert blocks[0].text == para.strip()
