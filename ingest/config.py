from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # http(s) URL -> server; ":memory:" -> in-process; anything else -> local folder (embedded)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "manuals"

    embed_backend: Literal["bge-m3", "hash"] = "bge-m3"
    embed_model: str = "BAAI/bge-m3"
    embed_batch_size: int = 16

    chunk_max_chars: int = 1500


def get_settings() -> Settings:
    return Settings()
