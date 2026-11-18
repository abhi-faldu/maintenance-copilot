"""Regression tests for ingest safety: pruning, doc_id collisions, partial runs, CLI checks."""

from __future__ import annotations

import shutil

import pytest
from qdrant_client import models

from ingest.__main__ import main
from ingest.embeddings import HashEmbedder
from ingest.pipeline import IngestError, discover_pdfs, ingest
from ingest.store import ChunkStore, make_client

MD_A = "# 1 A\n\nAlpha one.\n\n# 2 B\n\nAlpha two.\n"
MD_B = "# 1 B\n\nBeta one.\n"


@pytest.fixture
def env():
    emb = HashEmbedder()
    return ChunkStore(make_client(":memory:"), "test", emb.dim, emb.name), emb


def _statuses(report):
    return {d.doc_id: d.status for d in report.docs}


def test_deleted_pdf_is_pruned(env, make_pdf, tmp_path):
    st, emb = env
    make_pdf(MD_A, "corpus/A_EN.pdf")
    b = make_pdf(MD_B, "corpus/B_EN.pdf")
    ingest([tmp_path / "corpus"], emb, st)
    assert st.count("b-en") == 1

    b.unlink()
    report = ingest([tmp_path / "corpus"], emb, st)

    assert _statuses(report) == {"a-en": "skipped", "b-en": "pruned"}
    assert st.count("b-en") == 0 and st.count("a-en") == 2


def test_single_file_run_does_not_prune_others(env, make_pdf, tmp_path):
    st, emb = env
    a = make_pdf(MD_A, "corpus/A_EN.pdf")
    make_pdf(MD_B, "corpus/B_EN.pdf")
    ingest([tmp_path / "corpus"], emb, st)

    ingest([a], emb, st)
    assert st.count("b-en") == 1


def test_renamed_pdf_replaces_old_document(env, make_pdf, tmp_path):
    st, emb = env
    a = make_pdf(MD_A, "corpus/A_EN.pdf")
    ingest([tmp_path / "corpus"], emb, st)
    a.rename(a.with_name("A_v2_EN.pdf"))

    report = ingest([tmp_path / "corpus"], emb, st)
    assert _statuses(report) == {"a-v2-en": "ingested", "a-en": "pruned"}
    assert st.count() == 2


def test_same_name_in_two_folders_is_refused(env, make_pdf, tmp_path):
    st, emb = env
    make_pdf(MD_A, "one/Manual_EN.pdf")
    make_pdf(MD_B, "two/Manual_EN.pdf")
    with pytest.raises(IngestError, match="manual-en"):
        ingest([tmp_path / "one", tmp_path / "two"], emb, st)
    assert st.count() == 0  # refused before writing anything


def test_doc_id_owned_by_another_existing_file_is_refused(env, make_pdf, tmp_path):
    st, emb = env
    make_pdf(MD_A, "one/Manual_EN.pdf")
    make_pdf(MD_B, "two/Manual_EN.pdf")
    ingest([tmp_path / "one"], emb, st)
    with pytest.raises(IngestError, match="already used"):
        ingest([tmp_path / "two"], emb, st)
    assert st.count("manual-en") == 2  # the first document is untouched


def test_moved_pdf_is_accepted(env, make_pdf, tmp_path):
    st, emb = env
    a = make_pdf(MD_A, "one/Manual_EN.pdf")
    ingest([tmp_path / "one"], emb, st)
    (tmp_path / "two").mkdir()
    shutil.move(a, tmp_path / "two" / a.name)

    report = ingest([tmp_path / "two"], emb, st)
    assert _statuses(report) == {"manual-en": "ingested"}
    assert st.count() == 2


@pytest.mark.parametrize("damage", ["missing_point", "mixed_version"])
def test_partially_written_document_is_redone(env, make_pdf, damage):
    st, emb = env
    pdf = make_pdf(MD_A)
    ingest([pdf], emb, st)
    points, _ = st.client.scroll(st.collection, limit=1)
    if damage == "missing_point":
        st.client.delete(st.collection, points_selector=models.PointIdsList(points=[points[0].id]))
    else:
        st.client.set_payload(st.collection, {"doc_sha256": "older"}, points=[points[0].id])

    report = ingest([pdf], emb, st)
    assert report.docs[0].status == "ingested"
    assert st.count() == 2
    assert ingest([pdf], emb, st).docs[0].status == "skipped"


def test_uppercase_pdf_extension_is_found(make_pdf, tmp_path):
    make_pdf(MD_A, "corpus/Upper_EN.PDF")
    assert [p.name for p in discover_pdfs([tmp_path / "corpus"])] == ["Upper_EN.PDF"]


class _OtherModel(HashEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.name = "other-model"


def test_query_refuses_a_different_embedding_model(make_pdf, tmp_path, monkeypatch, capsys):
    db = tmp_path / "qdrant"
    client = make_client(str(db))
    emb = _OtherModel()
    ingest([make_pdf(MD_A)], emb, ChunkStore(client, "manuals", emb.dim, emb.name))
    client.close()

    monkeypatch.setenv("QDRANT_URL", str(db))
    monkeypatch.setenv("QDRANT_COLLECTION", "manuals")
    monkeypatch.setenv("EMBED_BACKEND", "hash")
    assert main(["query", "alpha"]) == 1
    assert "other-model" in capsys.readouterr().err


def test_query_runs_when_models_match(make_pdf, tmp_path, monkeypatch, capsys):
    db = tmp_path / "qdrant"
    client = make_client(str(db))
    emb = HashEmbedder()
    ingest([make_pdf(MD_A)], emb, ChunkStore(client, "manuals", emb.dim, emb.name))
    client.close()

    monkeypatch.setenv("QDRANT_URL", str(db))
    monkeypatch.setenv("QDRANT_COLLECTION", "manuals")
    monkeypatch.setenv("EMBED_BACKEND", "hash")
    assert main(["query", "Alpha one", "-k", "1"]) == 0
    assert "Alpha one" in capsys.readouterr().out
