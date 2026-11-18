# Maintenance Copilot

**An agentic RAG assistant for shop-floor maintenance. It reads the machine manuals, looks at live sensor data, asks a failure model, and answers with sources. Every answer is scored in CI.**

> Status (Nov 2026): week 1 in progress. Implemented: the `ingest/` pipeline (PDF → heading-aware sections → chunks → Qdrant) and the synthetic RA-3 manual (EN). Everything else below is design. Results tables are placeholders until the eval harness has run.
>
> Try the ingest without Docker or the 2 GB model (lexical stand-in embedder, local Qdrant folder):
> `QDRANT_URL=.qdrant-local EMBED_BACKEND=hash uv run python -m ingest run` then `... python -m ingest query "E-217"`.

---

## The problem

When a robot arm starts alarming at 2 a.m., the technician on shift has three disconnected sources of truth:

1. **The manual**: 200 pages of PDF, half of it in German, searched with Ctrl+F.
2. **The monitoring dashboard**: shows *that* vibration is 3σ above normal, not *why* or *what to do*.
3. **The failure model**: a probability score with no explanation attached.

A plain chatbot over the manuals makes this worse. It answers confidently, cites nothing, and has never seen the sensor data.

Maintenance Copilot connects the three. The technician asks *"Why is arm_02 alarming and what should I check first?"* The agent pulls the recent sensor window, retrieves the relevant troubleshooting section, optionally queries the failure model, and answers in the technician's language. Every claim points to a manual page or a data point.

## What it does

| Capability | How |
|---|---|
| **Document Q&A with citations** | Hybrid retrieval (BM25 + dense embeddings) over DE/EN manuals, reranked; every answer cites `doc, section, page` |
| **Live machine context** | Tool calls into the [IIoT Smart Factory Simulator](https://github.com/abhi-faldu/iiot-smart-factory-sim) API (latest readings, 15-min history, anomaly log) |
| **Failure-risk lookup** | Tool call into the [MLOps pipeline](https://github.com/abhi-faldu/anomaly-detection-MLops) `/predict` endpoint (champion XGBoost model) |
| **Bilingual** | German or English question, German or English manuals; answer comes back in the question's language |
| **Local-first** | Runs fully offline on Ollama, so no plant data leaves the network. A hosted LLM is optional and switched by one env var |
| **Measured, not vibes** | Eval harness with a labelled question set; GitHub Actions blocks a merge if faithfulness or retrieval quality drops below the floor |

## Architecture

```
                         ┌───────────────────────────────────────────┐
                         │  web/  Next.js 15 + React + TypeScript     │
                         │  ┌───────────────┐  ┌───────────────────┐  │
                         │  │ Chat (stream) │  │ Live sensor panel │  │
                         │  │ + citations   │  │ + anomaly feed    │  │
                         │  └───────┬───────┘  └─────────┬─────────┘  │
                         └──────────┼────────────────────┼────────────┘
                                    │ SSE                │ REST (proxied)
                         ┌──────────▼────────────────────┼────────────┐
                         │  copilot/  FastAPI             │            │
                         │                                │            │
                         │   ┌────────────────────────┐   │            │
                         │   │ Agent loop             │   │            │
                         │   │ plan → tool → observe  │   │            │
                         │   │ → answer (max 5 steps) │   │            │
                         │   └──┬──────────┬───────┬──┘   │            │
                         │      │          │       │      │            │
                         │  search_docs  get_    predict_ │            │
                         │      │        sensors  failure │            │
                         └──────┼──────────┼───────┼──────┼────────────┘
                                │          │       │      │
               ┌────────────────▼──┐  ┌────▼───────▼──────▼───────────┐
               │ Qdrant            │  │ Existing services (unchanged) │
               │ dense + BM25      │  │  iiot-smart-factory-sim :8000 │
               │ chunks w/ page    │  │  anomaly-detection-mlops:8001 │
               │ metadata          │  └───────────────────────────────┘
               └────────▲──────────┘
                        │
               ┌────────┴──────────┐        ┌────────────────────────┐
               │ ingest/           │        │ LLM backend            │
               │ PDF → sections →  │        │  Ollama (default)      │
               │ chunks → embed    │        │  or hosted API (opt.)  │
               └───────────────────┘        └────────────────────────┘
```

### Components

| Folder | Responsibility | Key choices |
|---|---|---|
| `ingest/` | Parse PDFs into sections that keep heading paths and page numbers, chunk them, embed them, upsert into Qdrant | Chunk on headings, not on fixed token windows: manuals are structured, so keep a troubleshooting table in one piece. Multilingual embedding model (`bge-m3`) so a German query finds an English chunk |
| `copilot/retrieval/` | Hybrid search, then reciprocal-rank fusion, then cross-encoder rerank, then top-k with metadata | BM25 catches exact error codes (`E-217`) that dense search misses |
| `copilot/agent/` | Tool-calling loop with a hard step limit, typed tool schemas, and structured citations | Hand-written loop of about 150 lines instead of a framework, so every step is visible in traces and tests |
| `copilot/tools/` | `search_docs`, `get_sensor_window`, `get_anomalies`, `predict_failure` | Thin, typed HTTP clients with timeouts. Tools return data, never prose |
| `copilot/api/` | `POST /chat` (SSE stream), `GET /health`, `GET /traces/{id}` | Each response carries `citations[]` and `tool_calls[]` for the UI |
| `web/` | Chat with inline citation chips, a side panel with live sensor sparklines and the anomaly feed, and a trace drawer showing which tools ran | Next.js App Router, TypeScript strict, Tailwind. Playwright smoke test |
| `eval/` | Question set, metric runners, report generator, CI gate | See the next section |

### Agent tools

| Tool | Input | Output | Backed by |
|---|---|---|---|
| `search_docs` | `query: str, lang?: "de"\|"en", k: int = 5` | `[{text, doc, section, page, score}]` | Qdrant |
| `get_sensor_window` | `arm_id, minutes ≤ 60` | per-sensor series + mean/std/last z-score | `GET /api/sensors/history` |
| `get_anomalies` | `arm_id?, since_minutes` | `[{ts, arm, sensor, value, z}]` | `GET /api/anomalies` |
| `predict_failure` | AI4I operating params (air/process temp K, rpm, torque, tool wear) | `{failure_probability, prediction, model_version}` | `POST /predict` |

**Two deliberate design decisions:**

- **No label leakage.** The simulator's anomaly log includes the injected ground-truth `fault_mode`. The `get_anomalies` tool **removes** that field before the agent sees it, and the eval harness uses it as the answer key for diagnosis questions. Otherwise the copilot would "diagnose" faults by reading the solution.
- **Honest model boundary.** The MLOps model was trained on AI4I 2020 features (rpm, torque, tool wear). The simulator emits temperature, vibration, and current. These are different machines, so `predict_failure` is exposed as a **what-if tool** ("at 1,800 rpm and 55 Nm, what's the failure risk?") and is never fed simulator readings through an invented mapping.

## Evaluation

The headline of this repo is that answer quality is a number, and CI enforces it, the same way the MLOps repo gates model promotion on PR-AUC.

**Question set** (`eval/questions.jsonl`, target 60, hand-written):

| Type | Example | Ground truth |
|---|---|---|
| Lookup (DE/EN) | "Welches Anzugsmoment hat die Flanschschraube am Gelenk 3?" | manual section + value |
| Troubleshooting | "Vibration on arm_02 spiked. What are the likely causes?" | manual section list |
| Live diagnosis | "Why is arm_01 alarming right now?" | simulator `fault_mode` (replay seed) |
| Cross-lingual | English question, answer only in a German manual | section ID |
| Refusal | "What's the warranty period for arm_03?" (not in any document) | must say *not found* |

**Metrics:**

| Metric | What it catches | CI floor (initial) |
|---|---|---|
| Retrieval hit@5 | right section not retrieved at all | ≥ 0.85 |
| Faithfulness | claims not supported by the cited chunks (LLM-judge + spot-checked by hand) | ≥ 0.80 |
| Citation precision | citations pointing at irrelevant chunks | ≥ 0.80 |
| Diagnosis accuracy | wrong `fault_mode` on live-diagnosis questions | ≥ 0.70 |
| Refusal rate on unanswerables | hallucinated answers | ≥ 0.90 |
| p95 latency (local, CPU) | unusable on shop-floor hardware | reported, not gated |

Floors get tightened once there is a baseline. Live-diagnosis questions run against `replay.py` with a fixed seed, so they are deterministic in CI.

**Results** (placeholder, filled in by `make eval`):

| Config | hit@5 | Faithfulness | Diagnosis acc. | p95 latency |
|---|---|---|---|---|
| Dense only | – | – | – | – |
| Hybrid + rerank | – | – | – | – |
| Hybrid + rerank + tools | – | – | – | – |

The ablation is the point: it shows what each layer actually buys, including if a layer turns out to buy nothing.

## Corpus

Real OEM manuals are copyrighted, so the repo ships with:

- **Synthetic manuals for the simulator's robot arm** (`RA-3`, DE + EN, about 40 pages each). They are written to match the simulator's fault modes (thermal drift, vibration spike, overcurrent) so live diagnosis can be checked against ground truth. They include tables, error-code lists, and torque specs, the formats that break naive chunking.
- **Openly licensed technical documents** where licenses allow redistribution. Each one is listed in `corpus/SOURCES.md` with its licence.
- A `corpus/private/` folder (git-ignored) for testing with your own PDFs.

## Running it

```bash
cp .env.example .env              # LLM_BACKEND=ollama by default
docker compose up -d              # qdrant, copilot, web (+ simulator & mlops via profiles)
make ingest                       # parse + embed corpus/
make eval                         # run the eval suite, write eval/report.md
```

UI at `http://localhost:3001`, API docs at `http://localhost:8010/docs`.

## Stack

Python 3.12 · FastAPI · Qdrant · bge-m3 embeddings · bge-reranker · Ollama (Qwen / Llama class models) · Next.js 15 · React · TypeScript · Tailwind · Docker Compose · GitHub Actions · pytest · Playwright

## Related projects

- [anomaly-detection-MLops](https://github.com/abhi-faldu/anomaly-detection-MLops): the failure model behind `predict_failure`
- [iiot-smart-factory-sim](https://github.com/abhi-faldu/iiot-smart-factory-sim): the live sensor stream behind `get_sensor_window` / `get_anomalies`

## License

MIT (code) · CC BY 4.0 (synthetic manuals and eval set)
