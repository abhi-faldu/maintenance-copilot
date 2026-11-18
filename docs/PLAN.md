# Maintenance Copilot — Build Plan

Target: demo-able v1 in **5 weeks at ~12 h/week** (fits around OTH + Lidl). Each week ends with something that runs and is committed. If time slips, cut from the bottom of the week, never the eval harness.

## Why this project (job-market evidence, Nov 2026)

From 31 tracked applications:

| Gap | Postings that asked for it | This repo covers it with |
|---|---|---|
| LLM / RAG / agents (~10 postings) | Silver Atena, softgate, Ata, Allianz GenAI, AssetMetrix (LLM eval), CEPRES, Tacto, ABB, BMW | hybrid RAG, tool-calling agent, eval harness |
| TypeScript / React frontend (~5) | Ata, Caterklick, Reinhausen, up2parts | `web/` in Next.js + TS strict |
| Already strong, reused as proof | Krones, WITRON, Hamm, up2parts, IfTA | integrates the IIoT sim + MLOps API, CI gate |

## Milestones

### Week 1 — Corpus + ingestion
- [x] Repo skeleton: `ingest/ copilot/ web/ eval/ corpus/`, `pyproject.toml`, ruff, pytest, `docker-compose.yml` with Qdrant
- [x] Write synthetic RA-3 manual (EN first): specs, error codes, troubleshooting per fault mode, maintenance intervals, torque table *(19 pages so far; target ~40)*
- [x] PDF → section parser keeping `doc / heading path / page`; heading-aware chunker; table kept whole
- [x] Embed with bge-m3, upsert to Qdrant; `make ingest` idempotent *(48 chunks, ~50 s embedding on laptop CPU; second run skips unchanged doc)*
- First dense-only observations (2026-11-18), to check against in week 2:
  - "Why is J2 vibrating?" → §7.3.2 / 7.3.1 / 7.3.3, all correct
  - German "Anzugsmoment Flanschschraube Gelenk 3" → right section (§9.1) only at rank 3, behind §4.2 and §3.2 → reranker candidate
  - Unanswerable "warranty period" scores 0.53, *higher* than the correct cross-lingual hit (0.525) → a raw similarity threshold cannot drive refusal
- [x] Tests: chunker never splits a table; every chunk has page metadata
- **Done when:** `make ingest` loads the corpus and a CLI query returns sensible chunks with page numbers

### Week 2 — Retrieval + eval harness (before the agent)
- [ ] BM25 index + dense search + reciprocal-rank fusion + cross-encoder rerank
- [ ] Write first 30 eval questions (lookup + troubleshooting + refusal)
- [ ] `eval/run.py`: hit@5, citation precision; writes `eval/report.md`
- [ ] Ablation: dense-only vs hybrid vs hybrid+rerank
- **Done when:** you have a real hit@5 number and know whether reranking helps. Write that finding down even if it's "no".

### Week 3 — Agent + tools
- [ ] LLM client abstraction (Ollama default, hosted optional) with tool-calling
- [ ] Agent loop: max 5 steps, typed tool schemas (Pydantic), structured `citations[]` + `tool_calls[]`
- [ ] Tools: `search_docs`, `get_sensor_window`, `get_anomalies` (**strip `fault_mode`**), `predict_failure`
- [ ] `POST /chat` with SSE streaming; trace stored per request
- [ ] Live-diagnosis questions using `replay.py` fixed seed; faithfulness judge; refusal check
- [ ] Tests: tool clients mocked; agent stops at step limit; leaked label never reaches the prompt
- **Done when:** "Why is arm_02 alarming?" returns a cited answer that matches the replay ground truth

### Week 4 — Frontend (TypeScript)
- [ ] Next.js App Router, TS strict, Tailwind
- [ ] Chat with streaming tokens + citation chips (click → page excerpt)
- [ ] Side panel: live sparklines per arm + anomaly feed (polls simulator API via copilot proxy)
- [ ] Trace drawer: which tools ran, with inputs/outputs
- [ ] Playwright smoke test (ask a question, see a citation)
- **Done when:** a 60-second screen recording tells the whole story without narration

### Week 5 — German, CI gate, polish
- [ ] German manual (translate + adapt, not machine-dump), cross-lingual questions → 60 total
- [ ] GitHub Actions: lint, unit tests, then eval on a small fixed model; fail below floors
- [ ] Fill README results table + ablation; `FINDINGS.md` with what didn't work
- [ ] Architecture diagram PNG, demo GIF, 2–3 LinkedIn images
- **Done when:** CI is green with the eval gate on, and README numbers come from `make eval`

## After v1 (only if a target role asks for it)
- Kubernetes/Helm manifests (up2parts, Conrad) — small add-on, high signal for those two
- Langfuse/OpenTelemetry tracing (observability angle for MLOps roles)
- Fine-tuned small reranker on the eval set

## Risks

| Risk | Mitigation |
|---|---|
| Local LLM too slow on laptop CPU for CI | CI uses smallest tool-capable model and only the 20 "gate" questions; full set runs locally |
| LLM-judge faithfulness is noisy | Fix judge model + temperature 0; hand-check 20 judgments and report agreement rate |
| Synthetic manual looks toy-like | Write it like a real one: error-code tables, safety notes, intervals, torque specs, cross-references |
| Scope creep into a framework | Hand-written agent loop; no LangChain/CrewAI unless a concrete need appears |

## CV / cover-letter lines (fill numbers only after they exist)

- DE: *Agentenbasierter RAG-Assistent für die Instandhaltung (FastAPI, Qdrant, Next.js/TypeScript): hybride Suche über DE/EN-Handbücher, Tool-Calls auf Live-Sensordaten und ML-Modell; Antwortqualität per Eval-Suite gemessen (Faithfulness __, Hit@5 __) und im CI als Merge-Gate erzwungen.*
- EN: *Agentic RAG maintenance assistant (FastAPI, Qdrant, Next.js/TypeScript): hybrid retrieval over DE/EN manuals, tool calls into live sensor data and a failure model; answer quality measured by an eval suite (faithfulness __, hit@5 __) and enforced as a CI merge gate.*
