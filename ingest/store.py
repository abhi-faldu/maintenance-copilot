"""Qdrant collection management and idempotent per-document replacement."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from qdrant_client import QdrantClient, models

from ingest.models import Chunk

DENSE = "dense"


def make_client(url: str) -> QdrantClient:
    if url == ":memory:":
        return QdrantClient(location=":memory:")
    if url.startswith(("http://", "https://")):
        return QdrantClient(url=url, timeout=30)
    return QdrantClient(path=url)  # embedded, persisted to a local folder


@dataclass
class SearchHit:
    score: float
    payload: dict


class ChunkStore:
    def __init__(self, client: QdrantClient, collection: str, dim: int, embed_model: str) -> None:
        self.client = client
        self.collection = collection
        self.dim = dim
        self.embed_model = embed_model

    def ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            info = self.client.get_collection(self.collection)
            vectors = info.config.params.vectors
            size = vectors[DENSE].size if isinstance(vectors, dict) else vectors.size
            if size != self.dim:
                raise RuntimeError(
                    f"collection {self.collection!r} has dim {size}, embedder has {self.dim}. "
                    "Use another QDRANT_COLLECTION or run `python -m ingest run --recreate`."
                )
            return
        self.client.create_collection(
            self.collection,
            vectors_config={
                DENSE: models.VectorParams(size=self.dim, distance=models.Distance.COSINE)
            },
        )
        with warnings.catch_warnings():
            # Embedded/in-memory Qdrant ignores payload indexes and warns; the server uses them.
            warnings.simplefilter("ignore", UserWarning)
            for field, schema in (
                ("doc_id", models.PayloadSchemaType.KEYWORD),
                ("lang", models.PayloadSchemaType.KEYWORD),
                ("section_id", models.PayloadSchemaType.KEYWORD),
            ):
                self.client.create_payload_index(self.collection, field, field_schema=schema)

    def recreate(self) -> None:
        if self.client.collection_exists(self.collection):
            self.client.delete_collection(self.collection)
        self.ensure_collection()

    @staticmethod
    def _doc_filter(doc_id: str) -> models.Filter:
        return models.Filter(
            must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))]
        )

    def _scroll(self, flt: models.Filter | None, fields: list[str]) -> list[models.Record]:
        out: list[models.Record] = []
        offset = None
        while True:
            batch, offset = self.client.scroll(
                self.collection,
                scroll_filter=flt,
                limit=256,
                offset=offset,
                with_payload=models.PayloadSelectorInclude(include=fields),
            )
            out.extend(batch)
            if offset is None:
                return out

    def doc_is_current(
        self, doc_id: str, doc_sha256: str, source_path: str, chunk_ids: set[str]
    ) -> bool:
        """True only if the stored points are exactly this version's chunks, all complete.

        Checking every point (not one sample) means an ingest interrupted between upsert
        batches, or before stale points were deleted, is detected and redone.
        """
        points = self._scroll(
            self._doc_filter(doc_id), ["doc_sha256", "embed_model", "source_path"]
        )
        if {str(p.id) for p in points} != chunk_ids:
            return False
        expected = (doc_sha256, self.embed_model, source_path)
        return all(
            (
                (p.payload or {}).get("doc_sha256"),
                (p.payload or {}).get("embed_model"),
                (p.payload or {}).get("source_path"),
            )
            == expected
            for p in points
        )

    def doc_sources(self) -> dict[str, set[str]]:
        """doc_id -> source paths recorded on its points ("" when not recorded)."""
        out: dict[str, set[str]] = {}
        for p in self._scroll(None, ["doc_id", "source_path"]):
            pl = p.payload or {}
            out.setdefault(pl.get("doc_id", ""), set()).add(pl.get("source_path", ""))
        return out

    def embed_models(self) -> set[str]:
        """Embedding model names recorded on the collection's points."""
        return {
            (p.payload or {}).get("embed_model", "") for p in self._scroll(None, ["embed_model"])
        }

    def delete_document(self, doc_id: str) -> int:
        n = self.count(doc_id)
        if n:
            self.client.delete(
                self.collection,
                points_selector=models.FilterSelector(filter=self._doc_filter(doc_id)),
            )
        return n

    def replace_document(
        self,
        doc_id: str,
        doc_sha256: str,
        chunks: list[Chunk],
        vectors: list[list[float]],
        source_path: str = "",
    ) -> int:
        """Upsert this document's chunks, then delete any of its points not in the new set."""
        assert len(chunks) == len(vectors)
        extra = {
            "doc_sha256": doc_sha256,
            "embed_model": self.embed_model,
            "source_path": source_path,
        }
        points = [
            models.PointStruct(id=c.chunk_id, vector={DENSE: v}, payload={**c.payload(), **extra})
            for c, v in zip(chunks, vectors, strict=True)
        ]
        for i in range(0, len(points), 128):
            self.client.upsert(self.collection, points=points[i : i + 128], wait=True)

        keep = {c.chunk_id for c in chunks}
        stale = [p.id for p in self._scroll(self._doc_filter(doc_id), []) if str(p.id) not in keep]
        if stale:
            self.client.delete(self.collection, points_selector=models.PointIdsList(points=stale))
        return len(stale)

    def count(self, doc_id: str | None = None) -> int:
        flt = self._doc_filter(doc_id) if doc_id else None
        return self.client.count(self.collection, count_filter=flt, exact=True).count

    def search(self, vector: list[float], k: int = 5, lang: str | None = None) -> list[SearchHit]:
        flt = (
            models.Filter(
                must=[models.FieldCondition(key="lang", match=models.MatchValue(value=lang))]
            )
            if lang
            else None
        )
        res = self.client.query_points(
            self.collection, query=vector, using=DENSE, limit=k, query_filter=flt, with_payload=True
        )
        return [SearchHit(p.score, p.payload or {}) for p in res.points]
