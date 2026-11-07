<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-RAG-1C3C3C?style=for-the-badge" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
</p>

<p align="center">
  <a href="https://github.com/AkinCodes/monster-game-resort-concierge/actions/workflows/test.yml"><img src="https://github.com/AkinCodes/monster-game-resort-concierge/actions/workflows/test.yml/badge.svg?branch=main" alt="Test Suite" /></a>
  <a href="https://github.com/AkinCodes/monster-game-resort-concierge/actions/workflows/evals.yml"><img src="https://github.com/AkinCodes/monster-game-resort-concierge/actions/workflows/evals.yml/badge.svg?branch=main" alt="Eval Gate" /></a>
</p>

# Monster Game Resort Concierge

A production-shaped AI concierge with a two-agent orchestrator (Planner → Executor), hybrid retrieval (BM25 + dense, reranked by a cross-encoder), two-tier hallucination detection at runtime (heuristic + NLI), and 4 tools with rich filtering, pagination and enum-typed parameters. It's built to show how retrieval, orchestration, memory and evaluation fit together.

It's a full backend, not a single API call: a cheap intent classifier that skips the planner for obvious greetings and questions, a retrieval pipeline with reranking, a Pydantic-validated plan, database-backed conversation memory, input and output guardrails, Prometheus metrics, and GitHub Actions CI.

> **Status:** portfolio project. It runs locally with uv or Docker and **isn't deployed**. AWS ECS config and scripts are included but haven't been run. The retrieval ablation below is a real measurement. The eval harness still runs against a mock pipeline, so there's no end-to-end score for the real concierge yet. Known gaps are listed under [Known Limitations](#known-limitations).

### The 6 Resorts

- **The Mummy Resort & Tomb-Service**
- **The Werewolf Lodge: Moon & Moor**
- **Castle Frankenstein: High Voltage Luxury**
- **Vampire Manor: Eternal Night Inn**
- **Zombie Bed & Breakfast: Bites & Beds**
- **Ghostly B&B: Spectral Stay**

<p align="center">
  <img src="assets/chat_ui_1.png" alt="Monster Game Resort Concierge — Spa Query" width="700" />
</p>
<p align="center">
  <img src="assets/chat_ui_2.png" alt="Monster Game Resort Concierge — Hotel Listing" width="700" />
</p>

---

## Technical Highlights

- **Hybrid retrieval with reranking** — BM25 keyword and dense vector candidates are merged, then reranked by a BGE cross-encoder. With the reranker off, the two lists are fused with weighted Reciprocal Rank Fusion.
- **Two-tier hallucination detection** — Tier 1: a fast heuristic (source attribution + token overlap + semantic similarity) on every knowledge answer. Tier 2: claim-level NLI with a cross-encoder when confidence isn't HIGH. An offline LLM-as-Judge script (`evals/llm_judge.py`, GPT-4o-mini, 1-5 scale) is included but isn't part of the runtime path. Intent pre-checks handle refusals and chitchat without scoring.
- **Multi-provider fallback** — OpenAI, Anthropic, OpenRouter and Ollama in a configurable order. OpenRouter reuses the OpenAI SDK with a `base_url` override. OpenRouter and Ollama are off unless enabled. If every provider fails, the user gets an apology message rather than an error.
- **4 tools** — `book_room`, `get_booking`, `search_amenities` and `search_events`. The planner picks a tool and its arguments through a JSON-planning prompt (not native function calling). `search_events` has 10 optional, enum-typed parameters with date ranges, tags, pagination, sorting and alias mapping, normalised server-side.
- **Tool limits** — 50 calls/min per tool (in memory, shared by all users) and a 10s timeout wrapper. The timeout can't interrupt the current tools: they're `async def` but never await, so a slow call runs to completion.
- **Two-agent orchestrator with a cheap classifier** — A zero-cost heuristic skips the planner for obvious intents (greetings, simple questions). For ambiguous or tool-related queries, a Planner LLM classifies intent and extracts arguments, then an Executor carries out the plan with focused, per-intent prompts.
- **Validated plans** — The planner's output is a Pydantic model. Parsing tries `json.loads`, then a scan for an embedded JSON object, then a keyword fallback. The planner can request JSON mode (`response_format`), but the tracing wrapper the app uses hides OpenAI's support for it, so it's never sent.
- **Input/output guardrails** — Prompt-injection patterns, PII redaction (email, US-format phone, card numbers, US SSN), a short block-list of coding and hacking requests, and output filtering (`app/core/guardrails.py`).
- **Database-backed conversation memory** — Messages persist across restarts. At 12 messages all 12 are summarised and deleted, keeping the last 5 summaries. Later planner, knowledge, clarify and chitchat prompts get the saved summary (screened for prompt-injection patterns) plus up to the latest 5 messages since then.
- **MCP-style tool endpoints** — REST endpoints at `/api/v1/mcp/*` for tool discovery, calls and server metadata, behind the same API-key auth as `/chat` and the same argument checks as the agent. They're not a spec-compliant MCP transport, and the agent calls tools directly rather than through them.
- **LLM tracing** — Router LLM calls are traced with latency, token counts and estimated cost via `LLMTracer`. The last 100 calls are kept in memory and served at `/api/v1/traces`.
- **Prompt management** — YAML-based versioned prompts (`prompts/*.yaml`) loaded by `app/core/prompt_loader.py`.
- **Anthropic prompt caching** — `cache_control` is set on Anthropic system prompts (the saving isn't measured).
- **Retrieval ablation study** — BM25 vs Dense vs Hybrid vs Full pipeline on a 13-query ground truth (`scripts/ablation_retrieval.py`).
- **RAG benchmark script** — Latency comparison against a LangChain RAG (`scripts/benchmark_rag.py`, optional MLflow logging). No results are published yet.
- **Eval history** — JSONL history with git SHA tagging and delta comparison in the retrieval, hallucination and benchmark scripts.
- **Infrastructure** — API-key auth, Prometheus metrics, a docker-compose stack (API, Postgres, Redis, Prometheus, Grafana, MLflow), ECS Fargate deploy config (not deployed), and GitHub Actions CI (lint, tests, offline eval checks).

---

## What the Agent Actually Does

```
Guest: "What's the spa situation at the Mummy Resort? Asking for a friend who's been wrapped up."
Guest: "Do you have WiFi at the Ghostly B&B? I need to ghost someone on social media."
Guest: "Book me a room at Werewolf Lodge — but not during full moon, I shed everywhere."
```

1. The request is authenticated (API key), and the message is validated and sanitised
2. The orchestrator runs input guardrails: prompt-injection patterns, an off-topic block-list, PII redaction
3. The cheap classifier checks if the intent is obvious (greeting → CHITCHAT, question → KNOWLEDGE). If it's ambiguous, the Planner LLM classifies the intent and extracts tool arguments
4. The Executor dispatches based on intent:
   - **KNOWLEDGE** → hybrid search (BM25 + dense candidates, reranked by a cross-encoder), top 5 chunks injected into a focused prompt
   - **TOOL** → validates args against an allowlist, runs the tool, LLM summarises the result
   - **CHITCHAT / CLARIFY** → direct LLM response with a persona prompt
5. For KNOWLEDGE responses: the hallucination detector scores the output (heuristic first, then claim-level NLI if confidence isn't HIGH)
6. Output guardrails check for leaked PII or character breaks
7. The response is returned with confidence scores, claim verification and intent metadata

**Sample `/chat` response (trimmed):**

```json
{
  "ok": true,
  "reply": "The Mummy Resort offers a Sand Exfoliation Treatment, Papyrus Wrap Therapy...",
  "session_id": "abc-123",
  "intent": "knowledge",
  "confidence": {"overall_score": 0.87, "level": "HIGH"},
  "claim_verification": null,
  "sources": ["amenities.txt:chunk_0"],
  "tools_used": [],
  "guardrail": null
}
```

---

## Ops Console — Live Agent Dashboard

A single-page operations console at `/console` for driving and observing the agent, built entirely over endpoints that already exist.

![Monster Ops Console](docs/images/ops-console.gif)

The main tabs:

- **Playground** — message the concierge and *watch it think*: the planner's intent, the confidence grade, which tool fired (and its args/result), the retrieved sources, and any guardrail flags, rendered live per turn. A second "Tools" mode calls any tool through the MCP-style endpoint and shows the raw result.
- **Sessions** — the Session Inspector (below), embedded as a tab.
- **Observability** — router LLM calls traced: provider, model, prompt/completion tokens, estimated **cost** and latency, with running totals.
- **Evals** — reads the offline report files: the **retrieval ablation** table (BM25 vs dense vs hybrid vs full pipeline, a real measurement), the hallucination-detector experiments, and the eval-harness pass rates and Recall/Precision@k cards (these two currently show mock-run data).

Self-contained dark-theme SPA (no frameworks) with traversal-safe static serving. Chat, session and MCP calls need an API key; the traces and evals endpoints are currently open. Open `http://localhost:8000/console` and enter an API key.

> Short demo loop, rendered from the real console UI with representative synthetic data.

---

## Session Inspector — Conversation Observability

A read-only dashboard at `/inspector` for replaying recent agent conversations: search a session, then step through the transcript and see **why** the agent did what it did.

![Session Inspector dashboard](docs/images/session-inspector.gif)

Each stored assistant turn is annotated with signals the orchestrator already computes:

- **Intent** — what the planner decided (KNOWLEDGE / TOOL / CLARIFY / CHITCHAT)
- **Confidence** — the hallucination detector's HIGH / MEDIUM / LOW grade and score
- **Tool calls** — name, arguments, and raw result (expandable JSON)
- **RAG sources** — which documents were retrieved to ground the answer
- **Guardrail flags** — output-guard blocks and PII-redaction notices (blocked inputs aren't recorded yet)
- **Usage** — latency and the executor call's token counts (cost per turn isn't filled in yet)

It complements the other two observability surfaces: `/metrics` (Prometheus) answers fleet-level questions, `/api/v1/traces` answers per-LLM-call questions, and the inspector gives a per-conversation, human-readable replay.

**How it works:** a `turn_metadata` table (schema v4) is written on each turn inside `orchestrator.handle()` (best-effort, it never blocks a response; skipped on the turn where history is summarised). Metadata for cleared messages is deleted, so the inspector shows recent turns only. Two auth-gated JSON endpoints back the UI:

| Endpoint | Purpose |
|---|---|
| `GET /inspector` | The dashboard (static HTML shell) |
| `GET /inspector/sessions?search=&page=&page_size=` | Paginated session list |
| `GET /inspector/sessions/{session_id}/transcript` | Full transcript + per-turn metadata |

**View it:** start the app, open `http://localhost:8000/inspector`, and enter an API key when prompted. Sessions contain synthetic data only.

> Short demo loop, rendered from the real inspector UI with representative synthetic session data.

---

## Architecture

```
+------------------+
|   Gradio Chat    |  :7861
|   (Gothic UI)    |
+--------+---------+
         |
+--------v---------+
|    FastAPI        |  :8000
|  /chat (thin)     |
+--------+---------+
         |
+--------v-----------------+
|   ConciergeOrchestrator  |
|                           |
|  Input Guardrails         |
|  ├─ Prompt injection      |
|  ├─ Off-topic block-list  |
|  └─ PII redaction         |
|                           |
|  Cheap Classifier         |
|  ├─ Greeting → CHITCHAT   |
|  ├─ Question → KNOWLEDGE  |
|  └─ Ambiguous → Planner   |
|                           |
|  Planner (LLM call #1)   |
|  └─ Intent + tool args    |
|                           |
|  Executor (LLM call #2)  |
|  ├─ _execute_knowledge()  |
|  ├─ _execute_tool()       |
|  ├─ _execute_chitchat()   |
|  └─ _execute_clarify()    |
|                           |
|  Hallucination Detection  |
|  ├─ Tier 1: Heuristic     |
|  └─ Tier 2: NLI (if !HIGH)|
|                           |
|  Output Guardrails        |
+--------+-----------------+
         |
+--------+--------+-----------+
|                 |            |
v                 v            v
+----------+  +----------+  +----------+
| Auth &   |  | LLM      |  | RAG      |
| Limits   |  | Router   |  | Pipeline |
|          |  |          |  |          |
| - API key|  | - OpenAI |  | - BM25   |
| - Per-   |  | - Anthro |  | - Dense  |
|   tool   |  | - OpenRtr|  | - Merge  |
+----------+  | - Ollama |
              | fallback |  | - Cross- |
              +----+-----+  | encoder  |
                   |        +-----+----+
              +----v----+         |
              | Tools   |<--------+
              | - book  |
              | - get   |
              | - search|
              | - events|
              +---+--+--+
                  |  |
                  v  v
           +------+ +-------+
           |SQLite| |  PDF  |
           +------+ +-------+
```

### Project Structure

```
app/
├── main.py                 # FastAPI app, thin /chat route, init helpers
├── config.py               # Settings from .env (pydantic BaseSettings)
├── core/
│   ├── tools.py            # Tool registry + book_room, get_booking, search_amenities, search_events (rate-limited)
│   ├── memory.py           # MemoryStore — DB-backed persistence + summarisation at 12 messages
│   ├── llm_providers.py    # ModelRouter — OpenAI / Anthropic / OpenRouter / Ollama fallback + prompt caching
│   ├── orchestrator.py     # Orchestrator — guardrails, cheap classifier, planner, executor, hallucination detection
│   ├── structured_output.py # JSON parsing helpers for planner output
│   ├── guardrails.py       # Input/output guardrails — injection patterns, PII redaction
│   ├── mcp_server.py       # MCP-style tool endpoints — discovery, calls, metadata
│   ├── observability.py    # LLM call tracing — latency, tokens, cost per call
│   ├── prompt_loader.py    # YAML prompt loader (versioned prompts from prompts/*.yaml)
│   ├── cost_tracker.py     # Cost estimation (prices in configs/model_pricing.yaml)
│   └── stream_client.py    # SSE streaming client (no server route yet)
├── rag/
│   ├── advanced_rag.py     # Hybrid RAG: BM25 + dense, cross-encoder reranking, RRF without the reranker
│   ├── vector_rag.py       # Base vector RAG implementation
│   ├── langchain_rag.py    # LangChain RAG (same interface, for benchmarking)
│   └── ingest_knowledge.py # CLI script to populate the knowledge base
├── database/
│   ├── db.py               # SQLite + PostgreSQL manager with schema versioning
│   └── cache_utils.py      # TTL cache for RAG search results (in-memory or Redis)
├── auth/
│   ├── jwt_auth.py         # JWT verification
│   ├── security.py         # API key manager (SHA-256 hashing, expiry, revocation, usage audit)
│   └── auth_mixins.py      # FastAPI dependency — API key (or JWT) auth
├── validation/
│   ├── hallucination.py    # 2-tier detection (heuristic + NLI), ClaimVerdict/ClaimVerification with to_dict()
│   ├── validators.py       # Input sanitisation and message validation
│   └── ragas_eval.py       # RAGAS wrapper (faithfulness, answer relevancy)
├── monitoring/
│   ├── metrics.py          # Prometheus counters and histograms
│   ├── logging_utils.py    # Structured JSON logging + custom exceptions
│   ├── mlflow_tracking.py  # MLflow experiment tracking
│   └── profile_utils.py    # Performance profiling decorator
├── console/                # Ops Console routes + static SPA
├── inspector/              # Session Inspector routes
├── data/
│   └── events.py           # 25 mock events + search_events() filter/sort/paginate function
├── api/
│   └── admin_routes.py     # Admin endpoints — API key CRUD
└── services/
    └── pdf_generator.py    # ReportLab PDF receipts

prompts/
├── planner.yaml                # Planner agent system prompt (versioned)
├── executor.yaml               # Executor agent system prompt (versioned)
└── summarization.yaml          # Conversation summarisation prompt (versioned)

evals/
├── hallucination_experiments.py # 5-experiment detector stress test with JSONL history
├── llm_judge.py                # Offline LLM-as-Judge evaluator (GPT-4o-mini, 1-5 scoring, --compare-heuristic)
├── eval_retrieval.py           # Retrieval quality metrics (MRR, Recall@K, Precision@K)
└── retrieval_ground_truth.json # 13-query ground truth answer key

scripts/
├── benchmark_rag.py            # Hybrid RAG vs LangChain latency benchmark (optional MLflow logging)
├── ablation_retrieval.py       # Retrieval ablation: BM25 vs Dense vs Hybrid vs Full
├── prep_finetune_data.py       # Generate train/valid JSONL from data/concierge_qa.json
├── finetune_mlx.py             # LoRA fine-tune TinyLlama-1.1B on Apple Silicon (MLX)
└── compare_rag_vs_finetune.py  # RAG vs fine-tuned latency and answer-length comparison
```

---

## Architecture Decisions & Trade-offs

### Why hybrid RAG instead of single-vector retrieval?

**Context:** Dense embeddings handle semantic similarity well but miss exact keyword matches, especially proper nouns like hotel names. BM25 catches those but misses semantic intent.

**Decision:** BM25 and dense retrieval both run, one after the other. Their candidates are merged and reranked by a cross-encoder (BGE). Without the reranker, the two lists are fused with weighted Reciprocal Rank Fusion.

**Trade-off (measured, not assumed):** On this corpus the cross-encoder reranker adds ~730ms/query on CPU (warm; the benchmark excludes cold start, but the app still loads the reranker on the first knowledge query) for a +0.04 MRR gain over dense-only (0.756 vs 0.718). That's a steep price for a narrow win, and on a 5-file corpus dense-only is hard to beat. The reranker should pay off as the corpus grows and candidates get more ambiguous, and a GPU should cut its cost (not measured here). For latency-sensitive paths the hybrid-no-reranker config (best Precision@5, single-digit ms) is the better default, though the app currently ships with the reranker on. See the [Retrieval Quality](#retrieval-quality) ablation and [`docs/blog/reranker-war-story.md`](docs/blog/reranker-war-story.md). Run `uv run python scripts/ablation_retrieval.py` to reproduce.

### Why SQLite by default, with PostgreSQL support?

**Context:** Designed for a single instance (for example, one Fargate task). Write volume is low (bookings, conversation messages), and the Docker image runs a single uvicorn worker, so there's one writer process.

**Decision:** SQLite as the default: zero operational overhead, no managed database, $0 cost. PostgreSQL is supported via `MRC_DATABASE_URL` for multi-instance setups, and the docker-compose file includes a Postgres service.

**Trade-off:** SQLite can't scale writes horizontally. For multi-instance or high-concurrency setups, switch to PostgreSQL (set `MRC_DATABASE_URL` to a `postgresql://` connection string).

### Why multi-provider fallback instead of just OpenAI?

**Context:** LLM provider outages are real. A single-provider system goes down when the provider does.

**Decision:** ModelRouter tries providers in a configurable priority order (default: OpenAI → Anthropic → OpenRouter → Ollama; OpenRouter and Ollama are off unless enabled). Failed calls route to the next provider.

**Trade-off:** Response characteristics vary across providers. The system normalises outputs via a shared LLMMessage/LLMResponse format, but latency and quality differ. Ollama runs locally at $0 but slower.

### Why hallucination scoring instead of binary guardrails?

**Context:** Binary block/allow loses information. A response that's 80% grounded should be treated differently from one that's 30% grounded.

**Decision:** A multi-signal confidence score (token overlap + semantic similarity + source attribution) on every knowledge (RAG) response, with HIGH/MEDIUM/LOW thresholds. The score is returned to the client alongside the response.

**Trade-off:** It adds computation per request. There's no extra LLM call, but it runs a small embedding model, plus an NLI model when confidence isn't HIGH, and every response carries metadata the frontend must handle.

### Why conversation summarisation at 12 messages?

**Context:** Long conversations overflow the LLM context window. Sending the full history gets expensive and eventually impossible.

**Decision:** At 12 messages all 12 are summarised (by an LLM if `MRC_OPENAI_API_KEY` or `OPENAI_API_KEY` is set, otherwise a regex summary) and deleted. The summary is saved in the database, keeping the last 5 summaries, and later prompts get it plus up to the latest 5 messages since then.

**Trade-off:** Clearing at 12 keeps prompts small, and the summary carries the key points forward. But a summary is lossy, especially the regex fallback, which keeps only intents and names, so specific early details can still be lost.

---

## Benchmarks & Metrics

See [EVALUATION.md](EVALUATION.md) for more detail on the ablation studies and reproduction steps.

### Retrieval Quality

**Retrieval ablation — 13-query ground truth (`reports/retrieval_ablation.json`, `scripts/ablation_retrieval.py`):**

| Config | Avg Latency (ms) | Precision@5 | MRR |
|--------|----------------:|------------:|----:|
| BM25 only | 0.1 | 0.169 | 0.449 |
| Dense only | 7.9 | 0.308 | 0.718 |
| Hybrid (no reranker) | 8.4 | **0.338** | 0.718 |
| **Full pipeline (hybrid + cross-encoder)** | 736.9 | 0.308 | **0.756** |

Measured on CPU (hardware not recorded). An honest read of this scoreboard, not a marketing one:

- **The full pipeline has the best MRR (0.756)**: the cross-encoder reranker edges out dense-only (0.718) on rank-of-first-relevant. With 13 queries, that gap comes down to 4 of them and isn't significance-tested.
- **But it's ~90x slower** (737ms vs 8ms on CPU). On a corpus this small the reranker's accuracy win is real but narrow, and the latency cost is steep. Hybrid-no-reranker matches dense on MRR and has the best Precision@5 (0.338) at single-digit-millisecond latency, which makes it the best accuracy/latency point for this corpus.
- These are the numbers *after* fixing the pipeline. On the earlier 8-query set, the original config (`bm25_weight=0.4`, RRF-truncated candidates fed to the reranker, cold cross-encoder inside the timed loop) was slower and had a lower MRR than dense-only. Full write-up: [`docs/blog/reranker-war-story.md`](docs/blog/reranker-war-story.md).

### Eval Harness

`scripts/eval_harness.py` has 20 cases across knowledge retrieval, tool use and chitchat. It currently runs against a deterministic mock pipeline, so its pass rates test the harness, not the concierge, and they aren't shown here. Running it end to end against the real orchestrator, RAG and tools is the next step.

### Hallucination Detection

A weighted confidence score on every knowledge response (`app/validation/hallucination.py`):

| Signal | Weight | Method |
|--------|--------|--------|
| Source attribution | 60% | Sentence-level grounding check (>= 30% overlap) |
| Token overlap | 20% | Token-level intersection ratio |
| Semantic similarity | 20% | Cosine similarity via `all-MiniLM-L6-v2` |

When confidence is MEDIUM or LOW, claim-level NLI verification runs via `cross-encoder/nli-deberta-v3-small` to check each claim against the source material.

| Confidence Level | Threshold |
|------------------|-----------|
| HIGH | >= 0.7 |
| MEDIUM | >= 0.4 |
| LOW | < 0.4 |

### Conversation Memory

`scripts/test_context_management.py` runs context-management experiments: with vs without history, token growth over a conversation, and window size. It needs an OpenAI key, and its output isn't saved yet, so no numbers are published here. The summarisation trigger at 12 messages is implemented in `app/core/memory.py` and tested in `tests/test_unit_core.py`.

### LLM Cost Tracking

Cost estimates use the prices in `configs/model_pricing.yaml` (per 1M tokens, USD):

| Model | Input | Output |
|-------|-------|--------|
| gpt-4o-mini | $0.15 | $0.60 |
| gpt-4o | $2.50 | $10.00 |
| gpt-4-turbo | $10.00 | $30.00 |
| gpt-3.5-turbo | $0.50 | $1.50 |
| claude-sonnet-4 | $3.00 | $15.00 |
| claude-3.5-sonnet | $3.00 | $15.00 |
| claude-3-haiku | $0.25 | $1.25 |
| llama3 (local) | $0.00 | $0.00 |

The tracer in `app/core/observability.py` uses its own price table, which differs slightly.

### Infrastructure

| Component | Detail |
|-----------|--------|
| Docker services | docker-compose defines 6 (API, PostgreSQL, Redis, Prometheus, Grafana, MLflow) |
| Test count | 366 tests in 24 files: 346 passed and 20 skipped in a local run on 05/11/2026 (the skipped ones are live LLM-judge tests that need an API key) |
| Orchestrator | Two-agent plan-then-execute (Planner classifies intent into knowledge / tool / clarify / chitchat, Executor carries out the plan) |
| LLM fallback chain | OpenAI -> Anthropic -> OpenRouter -> Ollama (configurable) |
| Deployment | Not deployed. ECS Fargate task definition included (1 vCPU, 2 GB RAM) |

---

## Quick Start

### Requirements

* Python 3.11 or 3.12
* [uv](https://docs.astral.sh/uv/) (recommended) or pip
* At least one LLM provider: OpenAI API key, Anthropic API key, OpenRouter API key, or local Ollama

### Setup

```sh
git clone https://github.com/AkinCodes/monster-game-resort-concierge.git
cd monster-game-resort-concierge
uv sync
cp .env.example .env   # Add your API key(s) and an MRC_JWT_SECRET_KEY of 32+ characters
```

### Run

```sh
uv run uvicorn app.main:app --reload
```

* **Health Check** → http://localhost:8000/health
* **API Docs** → http://localhost:8000/docs
* **Ops Console** → http://localhost:8000/console
* **Metrics** → http://localhost:8000/metrics
* **Web UI (Gradio)** → run `uv run python chat_ui.py`, then open http://localhost:7861

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Readiness stub (always returns ok) |
| `POST` | `/chat` | Main chat endpoint (orchestrator-based, returns confidence + intent) |
| `GET` | `/tools` | List registered tools and schemas |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/v1/traces` | Recent LLM call traces (latency, tokens, cost) |
| `GET` | `/api/v1/mcp/tools` | MCP-style tool discovery |
| `POST` | `/api/v1/mcp/call` | MCP-style tool call |
| `GET` | `/api/v1/mcp/info` | MCP-style server metadata |
| `GET` | `/console/evals` | Offline eval reports for the Ops Console |
| `POST` | `/admin/api-keys` | Create API key |
| `GET` | `/admin/api-keys` | List API keys |
| `DELETE` | `/admin/api-keys/{key_id}` | Revoke API key |
| `GET` | `/admin/api-keys/usage?key_id=` | View key usage audit log |

Only `/chat`, the `/api/v1/mcp/*` routes, the inspector data routes and `/admin/*` check the API key, and the admin routes accept any authenticated caller (there's no admin role). The other routes are open. That's fine locally, but they'd need locking down before any deployment.

### Authentication

**API Key** (as a Bearer token or an `X-API-Key` header):
```bash
curl -H "Authorization: Bearer $MRC_API_KEY" \
  http://localhost:8000/chat \
  -d '{"message": "Book a room for Mina at Vampire Manor"}' \
  -H "Content-Type: application/json"
```

JWTs are verified if sent, but the app doesn't issue them yet (there's no login route).

---

## Fine-Tuning (LoRA)

Scripts to compare RAG retrieval against a locally fine-tuned model:

```bash
# 1. Prepare training data from the Q&A set in data/concierge_qa.json (generates train/valid splits)
python scripts/prep_finetune_data.py

# 2. Fine-tune TinyLlama-1.1B with LoRA on Apple Silicon
pip install mlx-lm
python scripts/finetune_mlx.py

# 3. Compare RAG vs fine-tuned (latency and answer length)
python scripts/compare_rag_vs_finetune.py
```

Expected trade-offs (not measured yet): RAG should win on factual accuracy and freshness, since it can retrieve new docs without retraining, and fine-tuning should win on latency and cost. The comparison script currently measures latency and answer length only, and no run is saved.

---

## Testing

366 tests across 24 files covering API endpoints, API-key auth, guardrails, hallucination scoring, RAG retrieval, LLM provider fallback, the orchestrator, tools (including 43 `search_events` tests), per-tool rate limits, observability, MLflow tracking, and offline DeepEval checks. In a local run on 05/11/2026, 346 passed and 20 were skipped (live LLM-judge tests that need an API key).

```sh
uv run pytest --cov=app --cov-report=term-missing
```

CI runs on pushes to main and develop and on pull requests to main: flake8 + pytest (`test.yml`) and offline DeepEval checks (`evals.yml`). The DeepEval checks score the hallucination detector against canned mock responses, so they don't exercise the live pipeline. The live LLM-judge job only runs when an API key secret is set, and none is configured. There's no deploy step.

---

## Deployment

Not deployed yet. Everything below is config and scripts that haven't been run against AWS.

Tested locally on 05/11/2026: the image builds, the single container starts in prod mode (SQLite in `/data`), and the compose API runs against PostgreSQL and Redis, passing the health check and saving a booking. The Prometheus, Grafana and MLflow services weren't part of that test.

### Docker

```sh
# Single container
docker build -t monster-game-resort-concierge .
docker run -p 8000:8000 --env-file .env monster-game-resort-concierge

# Full stack (API + Postgres + Redis + Prometheus + Grafana + MLflow)
docker-compose up --build
```

Set `MRC_JWT_SECRET_KEY` (at least 32 characters) in `.env` first; the compose file passes it to the API and stops with an error if it's missing. Compose runs the API in prod mode, so `MRC_API_KEY` must be at least 32 characters and `MRC_OPENAI_API_KEY` must be set. Grafana starts with no dashboards provisioned.

### AWS (ECS Fargate)

Deployment config is in `deploy/aws/`:

* **ECS Fargate task definition** — 1 vCPU, 2 GB RAM; pulls the OpenAI, Anthropic, API and JWT keys from AWS Secrets Manager. The SQLite file lives inside the container, so data is lost when the task restarts; point `MRC_DATABASE_URL` at PostgreSQL for anything real
* **ECR push:** `./deploy/aws/ecr-push.sh <account-id> <region>`
* **Deploy:** `./deploy/aws/deploy.sh <account-id> <region>` (updates an existing ECS service; creating the cluster, service and IAM roles isn't scripted)
* **No automated deploy** — CI doesn't deploy

---

## Configuration

All settings via `.env` (prefix: `MRC_`). See `.env.example` for the common settings and `app/config.py` for the full list.

```env
MRC_LLM_PROVIDER_PRIORITY=openai,anthropic,openrouter,ollama
MRC_LLM_FALLBACK_ENABLED=true
MRC_OPENAI_MODEL=gpt-4o
MRC_HALLUCINATION_HIGH_THRESHOLD=0.7
MRC_MLFLOW_ENABLED=false
```

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_DATABASE_URL` | `sqlite:///./monster_resort.db` | Database connection string. Use `postgresql://user:pass@host:5432/dbname` to switch to PostgreSQL. |

SQLite is the default for local development (zero setup). For multi-instance setups, set `MRC_DATABASE_URL` to a PostgreSQL connection string.

### Redis Caching

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `MRC_REDIS_ENABLED` | `false` | Set to `true` to use Redis for RAG result caching. When disabled, an in-memory TTL cache is used. |

---

## Known Limitations

- **Not deployed** — it runs locally only. The ECS config hasn't been run.
- **No end-to-end eval yet** — the eval harness and the DeepEval CI checks run on a mock pipeline. The real numbers so far are the retrieval ablation and the hallucination-detector experiments.
- **Open endpoints** — the traces and evals routes have no auth. The MCP-style routes need an API key and run the same argument checks as the agent.
- **HTTP rate limiting** — SlowAPI is configured but not active. Only the per-tool limiter is enforced, in memory and shared by all users.
- **Conversation memory** — history is cleared every 12 messages and carried forward only as a short summary, so specific early details can be lost. Before it goes into a prompt, the summary is checked for prompt-injection patterns and left out if one matches.
- **JSON mode** — the planner asks for `response_format` only when the provider reports support, and the `LLMTracer` wrapper the app uses always reports `False`, so JSON mode is never sent.
- **Hallucination detector** — fast heuristic scoring (20/20/60 weights) on every knowledge response, with NLI claim verification only when confidence isn't HIGH. The style-mimic gap (wrong facts, right vocabulary) is meant to be caught by the NLI tier, but that isn't measured yet.
- **Cross-encoder reranking** — adds ~730ms/query on CPU (measured, warm) for a +0.04 MRR gain over dense-only on this small corpus, and the app currently ships with it on. Use the hybrid-no-reranker config on latency-sensitive paths (see [Retrieval Quality](#retrieval-quality)).
- **Guardrails are rule-based** — prompt-injection defence and PII redaction use pattern matching, not a trained classifier, and the off-topic check is a short block-list.
- **Knowledge base is static** — new content has to be added to `data/knowledge/` (ingested on the next start) or loaded with `ingest_knowledge.py`; there's no ingestion pipeline.

---

## Skills Demonstrated

- **LLM application architecture** — two-agent orchestrator (Planner → Executor), cheap intent classifier, Pydantic-validated plans, multi-provider routing with fallback
- **AI-to-tool interface design** — enum-typed tool schemas with 10 optional parameters, pagination, sorting, alias mapping for LLM output normalisation
- **Information retrieval** — hybrid search (BM25 + dense), cross-encoder reranking, weighted RRF, retrieval ablation study
- **Evaluation** — two-tier hallucination detection (heuristic + NLI), an offline LLM-as-Judge script, a RAGAS wrapper, JSONL eval history with git SHA tagging
- **MLOps** — optional MLflow experiment tracking, YAML prompt management, `--compare-last` delta tracking
- **Backend engineering** — API-key auth, input/output guardrails (injection patterns, PII redaction), per-tool rate limits, structured logging
- **Observability** — Prometheus metrics, per-call LLM tracing with cost estimates, a session inspector
- **Cloud and CI** — Docker and docker-compose, AWS ECS Fargate/ECR deploy config and scripts (not deployed yet), GitHub Actions CI
- **Parameter-efficient fine-tuning (LoRA)** — TinyLlama on Apple Silicon (MLX) and a RAG vs fine-tuned comparison script
- **Testing** — 366 tests in 24 files covering auth, guardrails, RAG, hallucination detection, LLM fallback, the orchestrator, `search_events`, MLOps, and offline DeepEval checks

---

## License

MIT — see [LICENSE](LICENSE).
