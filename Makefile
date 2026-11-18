.PHONY: install up down corpus ingest query test lint fmt

install:
	uv sync --extra embed

up:
	docker compose up -d qdrant

down:
	docker compose down

# Re-render the synthetic manuals from corpus/src/*.md into corpus/manuals/*.pdf
corpus:
	uv run python tools/build_manuals.py

# Idempotent: unchanged documents are skipped, changed ones are replaced in place
ingest:
	uv run python -m ingest run corpus/manuals

# make query Q="E-217 vibration alarm"
query:
	uv run python -m ingest query "$(Q)"

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .
