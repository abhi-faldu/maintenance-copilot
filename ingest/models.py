"""Data types passed between parser, chunker and store."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

# Fixed namespace so chunk IDs are stable across runs and machines (idempotent upserts).
CHUNK_NAMESPACE = uuid.UUID("6f1c3a52-6a0e-4c5e-9d0e-6b6b2f0c8a11")


@dataclass
class Block:
    """A paragraph or a table inside a section."""

    kind: Literal["text", "table"]
    text: str
    page_start: int
    page_end: int
    rows: list[list[str]] | None = None  # tables only, header row included if present
    has_header: bool = False

    @property
    def n_cols(self) -> int:
        return len(self.rows[0]) if self.rows else 0


@dataclass
class Section:
    section_id: str  # "7.2.1", "A", or "" for front matter
    title: str  # heading text as printed, e.g. "7.2.1 Symptoms"
    heading_path: list[str]  # titles from the chapter down to this section
    level: int
    page_start: int
    page_end: int
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ParsedDocument:
    doc_id: str
    title: str
    lang: str
    source: str  # file name
    sha256: str
    page_count: int
    sections: list[Section]


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    lang: str
    source: str
    section_id: str
    section_title: str
    heading_path: list[str]
    page_start: int
    page_end: int
    kind: Literal["text", "table", "mixed"]
    text: str

    @property
    def embed_text(self) -> str:
        """Text sent to the embedder: heading context first, so short chunks stay findable."""
        path = " > ".join(self.heading_path)
        return f"{self.doc_title}\n{path}\n\n{self.text}"

    def payload(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "lang": self.lang,
            "source": self.source,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "heading_path": self.heading_path,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "kind": self.kind,
            "text": self.text,
        }


def make_chunk_id(doc_id: str, section_id: str, ordinal: int, text: str) -> str:
    return str(uuid.uuid5(CHUNK_NAMESPACE, f"{doc_id}|{section_id}|{ordinal}|{text}"))
