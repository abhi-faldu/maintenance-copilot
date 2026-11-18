"""Embedding backends.

`BgeM3Embedder` is the real one: multilingual, so a German query can find an English
chunk. `HashEmbedder` is a dependency-free stand-in for tests and offline smoke runs; it
is lexical only (feature hashing of words and character trigrams) and must not be used to
judge retrieval quality.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
        self.name = f"hash-{dim}"

    def _features(self, text: str) -> list[str]:
        words = re.findall(r"[\wäöüß]+(?:-\d+)?", text.lower())
        grams = [w[i : i + 3] for w in words for i in range(max(len(w) - 2, 1))]
        return words + grams

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            v = [0.0] * self.dim
            for f in self._features(text):
                h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
                v[h % self.dim] += 1.0 if (h >> 63) else -1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


class BgeM3Embedder:
    def __init__(self, model: str = "BAAI/bge-m3", batch_size: int = 16) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "bge-m3 needs the 'embed' extra: uv sync --extra embed "
                "(or set EMBED_BACKEND=hash for an offline smoke run)"
            ) from e
        self._model = SentenceTransformer(model)
        self.name = model
        # Renamed to get_embedding_dimension in sentence-transformers 6.
        get_dim = getattr(self._model, "get_embedding_dimension", None)
        self.dim = get_dim() if get_dim else self._model.get_sentence_embedding_dimension()
        self.batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 32,
        )
        return [v.tolist() for v in vecs]


def embedder_name(backend: str, model: str) -> str:
    """Name an embedder records in Qdrant, known without loading the model."""
    if backend == "hash":
        return HashEmbedder().name
    if backend == "bge-m3":
        return model
    raise ValueError(f"unknown EMBED_BACKEND {backend!r}")


def make_embedder(backend: str, model: str, batch_size: int = 16) -> Embedder:
    if backend == "hash":
        return HashEmbedder()
    if backend == "bge-m3":
        return BgeM3Embedder(model, batch_size)
    raise ValueError(f"unknown EMBED_BACKEND {backend!r}")
