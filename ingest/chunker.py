"""Heading-aware chunking.

Rules
1. A chunk never crosses a section boundary: every chunk belongs to exactly one heading path.
2. A table is atomic. It is never split, even if it is longer than `max_chars`; an oversized
   table becomes a chunk of its own. A table that fits together with the paragraphs around
   it shares their chunk, so the sentence introducing it stays attached.
3. Paragraphs are packed greedily up to `max_chars`. A single paragraph longer than that is
   split on sentence boundaries; procedure steps (one per line) are split on line boundaries.
4. Page metadata is the min/max page of the blocks inside the chunk.
"""

from __future__ import annotations

import re

from ingest.models import Block, Chunk, ParsedDocument, Section, make_chunk_id

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])")


def _split_long_text(block: Block, max_chars: int) -> list[Block]:
    if len(block.text) <= max_chars:
        return [block]
    # Prefer line breaks (procedure steps), then sentences.
    units = block.text.split("\n") if "\n" in block.text else SENTENCE_END.split(block.text)
    sep = "\n" if "\n" in block.text else " "
    pieces, buf = [], ""
    for u in units:
        if buf and len(buf) + len(sep) + len(u) > max_chars:
            pieces.append(buf)
            buf = u
        else:
            buf = f"{buf}{sep}{u}" if buf else u
    if buf:
        pieces.append(buf)
    # Page info for a split paragraph: keep the block's range on every piece (conservative).
    return [Block("text", p, block.page_start, block.page_end) for p in pieces]


def _emit(section: Section, doc: ParsedDocument, blocks: list[Block], ordinal: int) -> Chunk:
    text = "\n\n".join(b.text for b in blocks)
    kinds = {b.kind for b in blocks}
    kind = "mixed" if len(kinds) > 1 else kinds.pop()
    return Chunk(
        chunk_id=make_chunk_id(doc.doc_id, section.section_id or section.title, ordinal, text),
        doc_id=doc.doc_id,
        doc_title=doc.title,
        lang=doc.lang,
        source=doc.source,
        section_id=section.section_id,
        section_title=section.title,
        heading_path=list(section.heading_path),
        page_start=min(b.page_start for b in blocks),
        page_end=max(b.page_end for b in blocks),
        kind=kind,
        text=text,
    )


def chunk_section(section: Section, doc: ParsedDocument, max_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[Block] = []

    def size(blocks: list[Block]) -> int:
        return sum(len(b.text) for b in blocks) + 2 * max(len(blocks) - 1, 0)

    def flush() -> None:
        nonlocal buf
        if buf:
            chunks.append(_emit(section, doc, buf, len(chunks)))
            buf = []

    for block in section.blocks:
        parts = [block] if block.kind == "table" else _split_long_text(block, max_chars)
        for part in parts:
            if buf and size([*buf, part]) > max_chars:
                flush()
            buf.append(part)
            if part.kind == "table" and len(part.text) > max_chars:
                flush()  # oversized table: alone, whole
    flush()
    return chunks


def chunk_document(doc: ParsedDocument, max_chars: int = 1500) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in doc.sections:
        chunks.extend(chunk_section(section, doc, max_chars))
    return chunks
