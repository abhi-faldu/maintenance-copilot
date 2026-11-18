"""parse -> chunk -> embed -> upsert, skipping documents that have not changed.

Each point records the absolute `source_path` of its PDF. That is what makes the run
safe to repeat:
- two different files that would get the same doc_id are refused instead of silently
  overwriting each other;
- a document whose PDF disappeared from a scanned folder is pruned, so a renamed or
  deleted manual stops being retrieved and cited.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ingest.chunker import chunk_document
from ingest.embeddings import Embedder
from ingest.parser import parse_pdf
from ingest.store import ChunkStore


class IngestError(Exception):
    pass


@dataclass
class DocResult:
    source: str
    doc_id: str
    status: str  # "ingested" | "skipped" | "pruned"
    chunks: int = 0
    removed: int = 0
    pages: int = 0


@dataclass
class IngestReport:
    docs: list[DocResult] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"{'status':9} {'chunks':>6} {'removed':>7} {'pages':>5}  source"]
        for d in self.docs:
            lines.append(f"{d.status:9} {d.chunks:6} {d.removed:7} {d.pages:5}  {d.source}")
        return "\n".join(lines)


def source_key(path: Path) -> str:
    return path.resolve().as_posix()


def discover_pdfs(paths: Iterable[str | Path]) -> list[Path]:
    found: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            # Case-insensitive on every OS: rglob("*.pdf") misses "X.PDF" on Linux.
            found.extend(sorted(f for f in p.rglob("*") if f.suffix.lower() == ".pdf"))
        elif p.suffix.lower() == ".pdf":
            found.append(p)
    return found


def _is_under(path: str, folder: Path) -> bool:
    return Path(path).is_relative_to(folder.resolve())


def ingest(
    paths: Iterable[str | Path],
    embedder: Embedder,
    store: ChunkStore,
    *,
    max_chars: int = 1500,
    force: bool = False,
    prune: bool = True,
) -> IngestReport:
    paths = list(paths)
    store.ensure_collection()
    report = IngestReport()
    pdfs = discover_pdfs(paths)
    docs = [(pdf, parse_pdf(pdf)) for pdf in pdfs]
    stored = store.doc_sources()

    # Refuse doc_id collisions before writing anything.
    by_id: dict[str, Path] = {}
    for pdf, doc in docs:
        if doc.doc_id in by_id:
            raise IngestError(
                f"{pdf} and {by_id[doc.doc_id]} both map to doc_id {doc.doc_id!r}; rename one."
            )
        by_id[doc.doc_id] = pdf
        others = {s for s in stored.get(doc.doc_id, set()) if s and s != source_key(pdf)}
        if any(Path(s).exists() for s in others):
            raise IngestError(
                f"doc_id {doc.doc_id!r} of {pdf} is already used by {sorted(others)[0]}; "
                "rename one of the files."
            )

    for pdf, doc in docs:
        key = source_key(pdf)
        chunks = chunk_document(doc, max_chars=max_chars)
        if not force and store.doc_is_current(
            doc.doc_id, doc.sha256, key, {c.chunk_id for c in chunks}
        ):
            report.docs.append(
                DocResult(pdf.name, doc.doc_id, "skipped", len(chunks), 0, doc.page_count)
            )
            continue
        vectors = embedder.embed([c.embed_text for c in chunks])
        removed = store.replace_document(doc.doc_id, doc.sha256, chunks, vectors, key)
        report.docs.append(
            DocResult(pdf.name, doc.doc_id, "ingested", len(chunks), removed, doc.page_count)
        )

    if prune:
        folders = [Path(p) for p in paths if Path(p).is_dir()]
        current = {source_key(pdf) for pdf in pdfs}
        for doc_id, sources in stored.items():
            if doc_id in by_id:
                continue
            gone = [
                s
                for s in sources
                if s and s not in current and any(_is_under(s, f) for f in folders)
            ]
            if gone and not any(Path(s).exists() for s in sources if s):
                n = store.delete_document(doc_id)
                report.docs.append(DocResult(Path(gone[0]).name, doc_id, "pruned", 0, n, 0))
    return report
