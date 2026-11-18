from __future__ import annotations

import shutil

import pytest

from ingest.embeddings import HashEmbedder
from ingest.pipeline import ingest
from ingest.store import ChunkStore, make_client
from tests.conftest import RA3_PDF


@pytest.fixture
def store():
    emb = HashEmbedder()
    return ChunkStore(make_client(":memory:"), "test", emb.dim, emb.name), emb


def test_ingest_is_idempotent(store, make_pdf):
    st, emb = store
    pdf = make_pdf("# 1 A\n\nAlpha text.\n\n# 2 B\n\nBeta text.\n")

    first = ingest([pdf], emb, st)
    n = st.count()
    second = ingest([pdf], emb, st)
    forced = ingest([pdf], emb, st, force=True)

    assert first.docs[0].status == "ingested" and n == first.docs[0].chunks == 2
    assert second.docs[0].status == "skipped"
    assert forced.docs[0].status == "ingested" and forced.docs[0].removed == 0
    assert st.count() == n


def test_changed_document_replaces_stale_chunks(store, make_pdf, tmp_path):
    st, emb = store
    v1 = make_pdf("# 1 A\n\nOld one.\n\n# 2 B\n\nOld two.\n\n# 3 C\n\nOld three.\n", "Doc_EN.pdf")
    ingest([v1], emb, st)
    assert st.count() == 3

    v2 = make_pdf("# 1 A\n\nNew one.\n", "Doc_EN.pdf")  # same doc_id, new content
    report = ingest([v2], emb, st)

    assert report.docs[0].removed == 3
    assert st.count() == 1
    (hit,) = st.search(emb.embed(["New one."])[0], k=5)
    assert hit.payload["text"] == "New one."


def test_documents_are_isolated(store, make_pdf):
    st, emb = store
    a = make_pdf("# 1 A\n\nFirst document.\n", "A_EN.pdf")
    b = make_pdf("# 1 B\n\nSecond document.\n", "B_EN.pdf")
    ingest([a, b], emb, st)
    ingest([make_pdf("# 1 A\n\nChanged.\n", "A_EN.pdf")], emb, st)
    assert st.count("b-en") == 1 and st.count("a-en") == 1


def test_dimension_mismatch_is_reported():
    client = make_client(":memory:")
    ChunkStore(client, "c", 384, "hash-384").ensure_collection()
    with pytest.raises(RuntimeError, match="dim 384"):
        ChunkStore(client, "c", 1024, "BAAI/bge-m3").ensure_collection()


def test_ra3_query_returns_cited_chunks(store, tmp_path):
    if not RA3_PDF.exists():
        pytest.skip("corpus PDF missing")
    st, emb = store
    pdf = shutil.copy(RA3_PDF, tmp_path / RA3_PDF.name)
    ingest([pdf], emb, st)

    hits = st.search(emb.embed(["E-217 J2 vibration alarm"])[0], k=5)
    sections = [h.payload["section_id"] for h in hits]
    assert {"6.2", "7.3.1", "7.3.2", "7.3.3"} & set(sections[:3])
    for h in hits:
        assert h.payload["page_start"] >= 1 and h.payload["source"] == RA3_PDF.name
