from __future__ import annotations

import pytest

from ingest.chunker import chunk_document, chunk_section
from ingest.models import Block, ParsedDocument, Section
from ingest.parser import parse_pdf
from tests.ingest.test_parser import long_table


def _doc(sections: list[Section]) -> ParsedDocument:
    return ParsedDocument("d", "Doc", "en", "d.pdf", "sha", 9, sections)


def _table(n_rows: int, page: int = 1, page_end: int | None = None) -> Block:
    rows = [["Code", "Text"]] + [[f"E-{i}", "x" * 40] for i in range(n_rows)]
    text = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return Block("table", text, page, page_end or page, rows=rows, has_header=True)


def _tables(doc: ParsedDocument) -> list[Block]:
    return [b for s in doc.sections for b in s.blocks if b.kind == "table"]


def test_oversized_table_is_one_chunk():
    big = _table(80)
    sec = Section(
        "6.2",
        "6.2 Codes",
        ["6 Alarms", "6.2 Codes"],
        2,
        3,
        4,
        [Block("text", "Intro.", 3, 3), big, Block("text", "Outro.", 4, 4)],
    )
    chunks = chunk_section(sec, _doc([sec]), max_chars=500)

    assert len(big.text) > 500
    holding = [c for c in chunks if big.text in c.text]
    assert len(holding) == 1
    assert holding[0].kind == "table"
    assert [c.text for c in chunks] == ["Intro.", big.text, "Outro."]


def test_small_table_stays_with_its_intro():
    t = _table(3)
    sec = Section(
        "7.2.2",
        "7.2.2 Causes",
        ["7.2.2 Causes"],
        3,
        11,
        11,
        [Block("text", "Likely causes, ranked:", 11, 11), t],
    )
    (chunk,) = chunk_section(sec, _doc([sec]), max_chars=1500)
    assert chunk.kind == "mixed"
    assert chunk.text.startswith("Likely causes, ranked:") and t.text in chunk.text


def test_long_paragraph_split_on_sentences_within_limit():
    para = " ".join(f"Sentence number {i} explains a step." for i in range(60))
    sec = Section("1", "1 X", ["1 X"], 1, 2, 2, [Block("text", para, 2, 2)])
    chunks = chunk_section(sec, _doc([sec]), max_chars=300)
    assert len(chunks) > 1
    assert all(len(c.text) <= 300 for c in chunks)
    assert " ".join(c.text for c in chunks) == para


def test_chunks_never_cross_sections():
    a = Section("1", "1 A", ["1 A"], 1, 1, 1, [Block("text", "alpha", 1, 1)])
    b = Section("2", "2 B", ["2 B"], 1, 1, 1, [Block("text", "beta", 1, 1)])
    chunks = chunk_document(_doc([a, b]), max_chars=1500)
    assert [(c.section_id, c.text) for c in chunks] == [("1", "alpha"), ("2", "beta")]


@pytest.mark.parametrize("max_chars", [200, 600, 1500, 4000])
def test_chunker_never_splits_a_table_ra3(ra3_doc, max_chars):
    chunks = chunk_document(ra3_doc, max_chars=max_chars)
    tables = _tables(ra3_doc)
    assert len(tables) >= 15
    for t in tables:
        holding = [c for c in chunks if t.text in c.text]
        assert len(holding) == 1, f"table on p{t.page_start} split or duplicated"
        assert holding[0].page_start <= t.page_start and holding[0].page_end >= t.page_end


def test_chunker_never_splits_a_page_spanning_table(make_pdf):
    doc = parse_pdf(make_pdf(f"# 1 Codes\n\n{long_table(60)}"))
    (table,) = _tables(doc)
    assert table.page_end > table.page_start
    chunks = chunk_document(doc, max_chars=300)
    (holding,) = [c for c in chunks if table.text in c.text]
    assert (holding.page_start, holding.page_end) == (table.page_start, table.page_end)


def test_every_chunk_has_page_metadata(ra3_doc):
    chunks = chunk_document(ra3_doc)
    assert chunks
    for c in chunks:
        assert isinstance(c.page_start, int) and isinstance(c.page_end, int)
        assert 1 <= c.page_start <= c.page_end <= ra3_doc.page_count, c.section_title
        p = c.payload()
        for key in ("doc_id", "source", "section_id", "heading_path", "page_start", "page_end"):
            assert p[key] not in (None, [], "") or key == "section_id", (key, c.section_title)


def test_chunk_ids_are_deterministic(ra3_doc):
    a = [c.chunk_id for c in chunk_document(ra3_doc)]
    b = [c.chunk_id for c in chunk_document(ra3_doc)]
    assert a == b and len(set(a)) == len(a)


def test_embed_text_carries_heading_path(ra3_doc):
    c = next(c for c in chunk_document(ra3_doc) if c.section_id == "7.3.1")
    assert "7 Troubleshooting > 7.3 Vibration spike (J2 vibration) > 7.3.1 Symptoms" in c.embed_text
