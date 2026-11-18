"""CLI.

python -m ingest run [PATH ...] [--force] [--recreate] [--no-prune]   parse, chunk, embed, upsert
python -m ingest query "TEXT" [-k 5] [--lang en]          dense search, prints citations
python -m ingest inspect FILE.pdf [--chunks]              show parsed sections/chunks (no Qdrant)
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from ingest.config import get_settings
from ingest.embeddings import embedder_name, make_embedder
from ingest.store import ChunkStore, make_client


def _store(settings, embedder) -> ChunkStore:
    client = make_client(settings.qdrant_url)
    return ChunkStore(client, settings.qdrant_collection, embedder.dim, embedder.name)


def cmd_run(args: argparse.Namespace) -> int:
    from ingest.pipeline import IngestError, ingest

    s = get_settings()
    embedder = make_embedder(s.embed_backend, s.embed_model, s.embed_batch_size)
    store = _store(s, embedder)
    if args.recreate:
        store.recreate()
    try:
        report = ingest(
            args.paths,
            embedder,
            store,
            max_chars=s.chunk_max_chars,
            force=args.force,
            prune=not args.no_prune,
        )
    except IngestError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(report.summary())
    print(f"collection {s.qdrant_collection!r}: {store.count()} points ({embedder.name})")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    s = get_settings()
    # Check before loading the embedding model, which takes a while.
    client = make_client(s.qdrant_url)
    if not client.collection_exists(s.qdrant_collection):
        print(
            f"No collection {s.qdrant_collection!r} at {s.qdrant_url}. "
            "Run `uv run python -m ingest run` first.",
            file=sys.stderr,
        )
        return 1
    # Query with the model the collection was built with, or the scores are meaningless.
    wanted = embedder_name(s.embed_backend, s.embed_model)
    stored = ChunkStore(client, s.qdrant_collection, 0, wanted).embed_models()
    if stored and stored != {wanted}:
        print(
            f"Collection {s.qdrant_collection!r} was embedded with {sorted(stored)}, "
            f"but the query would use {wanted!r}. Set EMBED_BACKEND/EMBED_MODEL to match, "
            "or re-ingest with `python -m ingest run --recreate`.",
            file=sys.stderr,
        )
        return 1
    embedder = make_embedder(s.embed_backend, s.embed_model, s.embed_batch_size)
    store = ChunkStore(client, s.qdrant_collection, embedder.dim, embedder.name)
    hits = store.search(embedder.embed([args.text])[0], k=args.k, lang=args.lang)
    for i, h in enumerate(hits, 1):
        p = h.payload
        pages = f"p. {p['page_start']}" + (
            f"-{p['page_end']}" if p["page_end"] != p["page_start"] else ""
        )
        print(f"[{i}] {h.score:.3f}  {p['source']}, §{p['section_id']} {pages}  ({p['kind']})")
        print(f"     {' > '.join(p['heading_path'])}")
        print(textwrap.indent(textwrap.shorten(p["text"], 300), "     "))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    from ingest.chunker import chunk_document
    from ingest.parser import parse_pdf

    doc = parse_pdf(args.file)
    print(f"{doc.title} [{doc.lang}] {doc.page_count} pages, {len(doc.sections)} sections")
    if args.chunks:
        for c in chunk_document(doc, get_settings().chunk_max_chars):
            print(
                f"§{c.section_id:7} p{c.page_start}-{c.page_end} {c.kind:5} {len(c.text):5}c  "
                f"{c.section_title}"
            )
    else:
        for sec in doc.sections:
            kinds = "".join("T" if b.kind == "table" else "." for b in sec.blocks)
            indent = "  " * max(sec.level - 1, 0)
            print(f"{indent}{sec.title}  p{sec.page_start}-{sec.page_end} {kinds}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="ingest PDFs into Qdrant")
    r.add_argument("paths", nargs="*", default=["corpus/manuals"])
    r.add_argument("--force", action="store_true", help="re-embed even if unchanged")
    r.add_argument("--recreate", action="store_true", help="drop and recreate the collection")
    r.add_argument(
        "--no-prune",
        action="store_true",
        help="keep documents whose PDF is no longer in the scanned folders",
    )
    r.set_defaults(func=cmd_run)

    q = sub.add_parser("query", help="dense search")
    q.add_argument("text")
    q.add_argument("-k", type=int, default=5)
    q.add_argument("--lang", choices=["en", "de"])
    q.set_defaults(func=cmd_query)

    i = sub.add_parser("inspect", help="show parsed structure of one PDF")
    i.add_argument("file")
    i.add_argument("--chunks", action="store_true")
    i.set_defaults(func=cmd_inspect)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
