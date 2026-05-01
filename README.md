<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-RAG-1C3C3C?style=for-the-badge" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS_ECS-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white" />
</p>

# Monster Game Resort Concierge

A fully wired AI concierge system with hybrid RAG (BM25 + dense + cross-encoder reranking), real-time hallucination scoring, multi-provider LLM fallback, and function-calling tool execution — built to demonstrate how retrieval, agent loops, memory, monitoring, and deployment work together in a production-shaped architecture.

This isn't a wrapper around an API call. It's a complete backend: a 3-stage retrieval pipeline, an agent loop with tool calling, database-backed conversation memory with automatic summarization, hallucination detection on every response, and CI/CD to AWS — all behind JWT auth, rate limiting, and Prometheus observability.

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

- **3-stage hybrid RAG pipeline** — BM25 keyword + dense vector retrieval, fused via Reciprocal Rank Fusion, then reranked by a cross-encoder. Not a single-vector lookup.
- **Hallucination detection on every response** — token overlap + semantic similarity + source attribution scoring → HIGH / MEDIUM / LOW confidence returned with every answer.
- **3-provider LLM fallback** — OpenAI → Anthropic → Ollama. If one goes down, the next takes over automatically. No user-facing errors during provider outages.
- **Function-calling agent** — Tool registry with schema generation, input validation against a 6-property allowlist, and async execution with timing and structured logging.
- **Tool sandboxing** — 10s timeout and 50/min rate limiting per tool to prevent runaway or abusive calls.
- **Two-agent orchestrator** — Planner classifies intent (knowledge/tool/clarify/chitchat), Executor carries out the plan with structured output parsing and retry logic.
- **Native structured outputs** — `response_format` support with a 3-level fallback chain (native JSON mode → regex extraction → raw).
- **Input/output guardrails** — Prompt injection defense, PII redaction, topic boundary enforcement, and output filtering (`app/core/guardrails.py`).
- **Database-backed conversation memory** — Messages persist across restarts. Automatic summarization at 12 messages compresses context while preserving conversational continuity.
- **MCP tool server** — Model Context Protocol endpoints at `/api/v1/mcp/*` for tool discovery, execution, and server metadata.
- **LLM observability & tracing** — Per-call tracing with latency, token counts, and cost via `LLMTracer`; query traces at `/api/v1/traces`.
- **Prompt management** — YAML-based versioned prompts (`prompts/*.yaml`) loaded by `app/core/prompt_loader.py`.
- **Anthropic prompt caching** — `cache_control` on system prompts to reduce latency and cost on repeated calls.
- **Head-to-head RAG benchmark** — Custom hybrid pipeline vs LangChain RAG, tracked via MLflow. Run `uv run python scripts/benchmark_rag.py` to reproduce.
- **Retrieval ablation study** — BM25 vs Dense vs Hybrid vs Full pipeline comparison (`scripts/ablation_retrieval.py`).
- **Persistent eval store** — JSONL eval history with git SHA tagging and delta comparison across runs.
- **Full production stack** — JWT + API key auth, rate limiting, Prometheus/Grafana, ECS Fargate deployment, GitHub Actions CI/CD.

---

## What the Agent Actually Does

```
Guest: "What's the spa situation at the Mummy Resort? Asking for a friend who's been wrapped up."
Guest: "Do you have WiFi at the Ghostly B&B? I need to ghost someone on social media."
Guest: "Book me a room at Werewolf Lodge — but not during full moon, I shed everywhere."
```

1. Message is validated, sanitized, and authenticated (JWT or API key)
2. RAG pipeline runs hybrid search — BM25 keyword + dense vector retrieval — fused via Reciprocal Rank Fusion, then reranked by a cross-encoder
3. Top 5 context chunks are injected into the system prompt with source attribution tags
4. LLM (OpenAI / Anthropic / Ollama) generates a response and decides whether to call a tool
5. Tool executes: validates hotel against a 6-property allowlist, checks dates, writes to SQLite, generates a PDF receipt
6. Tool results feed back to the LLM for a synthesis response
7. Hallucination detector scores the final output (context overlap + semantic similarity + source attribution) and assigns HIGH / MEDIUM / LOW confidence
8. Response streams back to the Gradio chat UI with confidence metadata
9. Prometheus captures request latency, token usage, RAG retrieval time, and confidence distribution

**Sample `/chat` response:**

```json
{
  "response": "The Mummy Resort offers a Sand Exfoliation Treatment, Papyrus Wrap Therapy...",
  "confidence": "HIGH",
  "confidence_score": 0.87,
  "provider": "openai",
  "model": "gpt-4o",
  "session_id": "abc-123",
  "request_id": "req-456"
}
```

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
|   /chat  /metrics |
+--------+---------+
         |
+--------+--------+-----------+
|                 |            |
v                 v            v
+----------+  +----------+  +----------+
| Auth &   |  | LLM      |  | RAG      |
| Rate     |  | Router   |  | Pipeline |
| Limiting |  |          |  |          |
| - JWT    |  | - OpenAI |  | - BM25   |
| - API key|  | - Anthro |  | - Dense  |
| (SHA-256)|  | - Ollama |  | (ChromaDB|
| - SlowAPI|  | Auto-fall|  | - RRF    |
| - Input  |  |   back   |  | - Cross- |
| sanitize |  +----+-----+  |  encoder  |
+----------+       |        | reranking |
                   v        +-----+----+
         +---------+---+          |
         | Agent Loop   |<--------+
         | (tool calls) |
         +---+-----+---+
             |     |
             v     v
    +--------+  +--+------+
    | SQLite |  |   PDF   |
    |Bookings|  | Receipts|
    +--------+  +---------+
```

### Project Structure

```
app/
├── main.py                 # FastAPI app, agent loop, /chat endpoint
├── config.py               # Settings from .env (pydantic BaseSettings)
├── core/
│   ├── tools.py            # Tool registry + book_room, get_booking, search_amenities (sandboxed)
│   ├── memory.py           # MemoryStore — DB-backed persistence + auto-summarization
│   ├── llm_providers.py    # ModelRouter — OpenAI / Anthropic / Ollama fallback + prompt caching
│   ├── orchestrator.py     # Two-agent orchestrator — Planner + Executor
│   ├── structured_output.py # JSON output parser with 3-level fallback chain
│   ├── guardrails.py       # Input/output guardrails — injection defense, PII redaction
│   ├── mcp_server.py       # MCP tool server — discovery, execution, metadata
│   ├── observability.py    # LLM call tracing — latency, tokens, cost per call
│   ├── prompt_loader.py    # YAML prompt loader (versioned prompts from prompts/*.yaml)
│   ├── cost_tracker.py     # Per-request cost estimation across 8 models
│   └── stream_client.py    # SSE streaming client
├── rag/
│   ├── advanced_rag.py     # Hybrid RAG: BM25 + dense + RRF + cross-encoder
│   ├── vector_rag.py       # Base vector RAG implementation
│   ├── langchain_rag.py    # LangChain RAG (same interface, for benchmarking)
│   └── ingest_knowledge.py # CLI script to populate the knowledge base
├── database/
│   ├── db.py               # SQLite + PostgreSQL manager with WAL, migrations, auto-backups
│   └── cache_utils.py      # TTL cache for RAG search results (in-memory or Redis)
├── auth/
│   ├── jwt_auth.py         # JWT token creation and verification
│   ├── security.py         # API key manager (SHA-256 hashing, rotation, audit)
│   ├── auth_mixins.py      # FastAPI dependency — JWT or API key auth
│   └── users_db.py         # Demo user store
├── validation/
│   ├── hallucination.py    # Confidence scoring (overlap + semantic + attribution)
│   ├── validators.py       # Input sanitization and message validation
│   └── ragas_eval.py       # RAGAS evaluation framework
├── monitoring/
│   ├── metrics.py          # Prometheus counters, histograms, gauges
│   ├── logging_utils.py    # Structured JSON logging + custom exceptions
│   ├── mlflow_tracking.py  # MLflow experiment tracking
│   └── profile_utils.py    # Performance profiling decorator
├── api/
│   └── admin_routes.py     # Admin endpoints — API key CRUD
└── services/
    └── pdf_generator.py    # ReportLab PDF receipts

prompts/
├── planner.yaml                # Planner agent system prompt (versioned)
├── executor.yaml               # Executor agent system prompt (versioned)
└── summarization.yaml          # Conversation summarization prompt (versioned)

scripts/
├── benchmark_rag.py            # Hybrid RAG vs LangChain benchmark (MLflow tracked)
├── ablation_retrieval.py       # Retrieval ablation: BM25 vs Dense vs Hybrid vs Full
├── prep_finetune_data.py       # Generate train/valid JSONL from knowledge base
├── finetune_mlx.py             # LoRA fine-tune TinyLlama-1.1B on Apple Silicon (MLX)
└── compare_rag_vs_finetune.py  # Head-to-head: RAG vs fine-tuned vs combined
```

---

## Architecture Decisions & Trade-offs

### Why hybrid RAG instead of single-vector retrieval?

**Context:** Dense embeddings handle semantic similarity well but miss exact keyword matches — especially proper nouns like hotel names. BM25 catches those but misses semantic intent.

**Decision:** Three-stage pipeline — BM25 + dense retrieval in parallel, fused via Reciprocal Rank Fusion, then reranked by a cross-encoder (BGE).

**Trade-off:** Adds ~50ms latency per query vs single-vector search. The precision improvement justifies the cost — proper noun queries (e.g., "What does Vampire Manor offer?") went from partial matches to consistent top-1 hits. Run `uv run python scripts/benchmark_rag.py` to compare against a LangChain baseline.

### Why SQLite by default, with PostgreSQL support?

**Context:** Single-instance deployment on ECS Fargate. Write volume is low (bookings, conversation messages). No concurrent multi-writer workload in the default case.

**Decision:** SQLite with WAL mode as the default — zero operational overhead, no managed database dependency, $0 cost. PostgreSQL is supported via `MRC_DATABASE_URL` for multi-instance deployments. `docker-compose up` provisions Postgres automatically.

**Trade-off:** SQLite cannot horizontally scale writes. For multi-instance or high-concurrency deployments, switch to PostgreSQL (set `MRC_DATABASE_URL` to a `postgresql://` connection string).

### Why multi-provider fallback instead of just OpenAI?

**Context:** LLM provider outages are real. A single-provider system goes down when the provider does.

**Decision:** ModelRouter tries providers in configurable priority order (default: OpenAI → Anthropic → Ollama). Failed calls automatically route to the next provider.

**Trade-off:** Response characteristics vary across providers. The system normalizes outputs via a shared LLMMessage/LLMResponse format, but latency and quality differ. Ollama runs locally at $0 but slower.

### Why hallucination scoring instead of binary guardrails?

**Context:** Binary block/allow loses information. A response that's 80% grounded should be treated differently than one that's 30% grounded.

**Decision:** Multi-signal confidence score (token overlap + semantic similarity + source attribution) on every response, with HIGH/MEDIUM/LOW thresholds. Score is returned to the client alongside the response.

**Trade-off:** Adds computation per request. The scoring is lightweight (no additional LLM call), but it means every response carries metadata the frontend must handle.

### Why conversation summarization at 12 messages?

**Context:** Long conversations overflow the LLM context window. Sending the full history becomes expensive and eventually impossible.

**Decision:** At 12 messages, the system summarizes the oldest messages into a rolling summary (LLM-based, with regex fallback if the LLM is unavailable). Old messages are pruned. The summary persists in the database.

**Trade-off:** Summarization loses detail. The threshold of 12 balances context preservation against token cost — early enough to stay within budget, late enough to capture meaningful conversation.

---

## Benchmarks & Metrics

See [EVALUATION.md](EVALUATION.md) for full ablation studies, failure analysis, and reproduction instructions.

### Retrieval Quality

8-query evaluation over the resort knowledge base (`reports/retrieval_metrics.json`):

| Metric | @3 | @5 | @10 |
|--------|-----|-----|------|
| Recall | 0.469 | 0.625 | 1.000 |
| Precision | 0.208 | 0.175 | 0.125 |
| **MRR** | **0.362** | | |

### Eval Harness

20-case evaluation across knowledge retrieval, tool use, and chitchat (`reports/eval_report.json`):

| Category | Cases | Pass Rate |
|----------|-------|-----------|
| Knowledge Retrieval | 11 | 54.5% |
| Tool Use | 6 | 0.0% |
| Chitchat | 3 | 66.7% |
| **Overall** | **20** | **40.0%** |

| Aggregate Metric | Value |
|------------------|-------|
| Avg hallucination score | 0.60 |
| Avg retrieval relevance | 0.379 |
| Tool selection accuracy | 80.0% |

### Hallucination Detection

Weighted confidence score on every response (`app/validation/hallucination.py`):

| Signal | Weight | Method |
|--------|--------|--------|
| Semantic similarity | 50% | Cosine similarity via `all-MiniLM-L6-v2` |
| Token overlap | 30% | Token-level intersection ratio |
| Source attribution | 20% | Sentence-level grounding check (>= 30% overlap) |

| Confidence Level | Threshold |
|------------------|-----------|
| HIGH | >= 0.7 |
| MEDIUM | >= 0.4 |
| LOW | < 0.4 |

### Conversation Memory

Results from context management experiments (`scripts/test_context_management.py`):

| Experiment | Finding |
|------------|---------|
| With vs without history | 188 vs 95 tokens; without history the model loses name, room, and prior context |
| Token scaling (0 to 20 turns) | 12.5x prompt token increase |
| Auto-summarisation trigger | Fires at 12 messages, compresses older messages to a rolling summary |
| Window size (last-2 vs all-10) | Last-2 loses dietary restrictions from message 1; all-10 retains everything |

### LLM Cost Tracking

Per-request cost estimates from `app/core/cost_tracker.py` (prices per 1M tokens, USD):

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

### Infrastructure

| Component | Detail |
|-----------|--------|
| Docker services | 6 (API, PostgreSQL, Redis, Prometheus, Grafana, MLflow) |
| Test count | 193 tests across 20 files |
| Orchestrator | Two-agent plan-then-execute (Planner classifies intent into knowledge / tool / clarify / chitchat, Executor carries out the plan) |
| LLM fallback chain | OpenAI -> Anthropic -> Ollama |
| Deployment | ECS Fargate (1 vCPU, 2 GB RAM) |

---

## Quick Start

### Requirements

* Python 3.11+
* [uv](https://docs.astral.sh/uv/) (recommended) or pip
* At least one LLM provider: OpenAI API key, Anthropic API key, or local Ollama

### Setup

```sh
git clone https://github.com/AkinCodes/monster-game-resort-concierge.git
cd monster-game-resort-concierge
uv sync
cp .env.example .env   # Add your API key(s)
```

### Run

```sh
uv run uvicorn app.main:app --reload
```

* **Health Check** → http://localhost:8000/health
* **API Docs** → http://localhost:8000/docs
* **Web UI (Gradio)** → http://localhost:8000/gradio *(if enabled)*
* **Metrics** → http://localhost:8000/metrics

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/ready` | Readiness check |
| `POST` | `/login` | Get JWT access + refresh tokens |
| `POST` | `/chat` | Main chat endpoint (returns confidence scores + provider used) |
| `POST` | `/chat/stream` | Streaming chat via SSE |
| `GET` | `/tools` | List registered tools and schemas |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/v1/traces` | Recent LLM call traces (latency, tokens, cost) |
| `GET` | `/api/v1/mcp/tools` | MCP tool discovery |
| `POST` | `/api/v1/mcp/call` | MCP tool execution |
| `GET` | `/api/v1/mcp/info` | MCP server metadata |
| `POST` | `/admin/api-keys` | Create API key |
| `GET` | `/admin/api-keys` | List API keys |
| `DELETE` | `/admin/api-keys/{key_id}` | Revoke API key |
| `GET` | `/admin/api-keys/{key_id}/usage` | View key usage audit log |

### Authentication

**API Key:**
```bash
curl -H "Authorization: Bearer $MRC_API_KEY" \
  http://localhost:8000/chat \
  -d '{"message": "Book a room for Mina at Vampire Manor"}' \
  -H "Content-Type: application/json"
```

**JWT Bearer Token:**
```bash
# Login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo"}'

# Use the token
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/chat \
  -d '{"message": "What amenities does the Werewolf Lodge offer?"}' \
  -H "Content-Type: application/json"
```

---

## Fine-Tuning (LoRA)

Compare RAG retrieval against a locally fine-tuned model to understand the trade-offs:

```bash
# 1. Prepare training data from the knowledge base (generates train/valid splits)
python scripts/prep_finetune_data.py

# 2. Fine-tune TinyLlama-1.1B with LoRA on Apple Silicon (~20 min on M1 Pro)
pip install mlx-lm
python scripts/finetune_mlx.py

# 3. Head-to-head evaluation: RAG vs fine-tuned vs combined
python scripts/compare_rag_vs_finetune.py
```

RAG wins on factual accuracy and freshness (can retrieve new docs without retraining). Fine-tuning wins on latency and cost (no API calls, no retrieval step). The comparison script produces a metrics table showing where each approach excels.

---

## Testing

20 test files covering API endpoints, authentication, guardrails, hallucination detection, RAG retrieval, LLM provider fallback, orchestrator, tool execution, MLflow tracking, and RAGAS evaluation.

```sh
uv run pytest --cov=app --cov-report=term-missing
```

| Category | Files | What's Covered |
|----------|-------|----------------|
| API & Auth | 4 | Endpoints, JWT flow, API key lifecycle, rate limiting |
| RAG Pipeline | 3 | Retrieval accuracy, LangChain parity, unit chunking |
| LLM & Agent | 2 | Provider fallback, hallucination scoring |
| Booking & Tools | 2 | Booking creation, tool registry validation |
| MLOps | 2 | MLflow experiment tracking, RAGAS evaluation |
| Infrastructure | 1 | Cache utilities |

CI runs on every push to main via GitHub Actions (lint + test + deploy).

---

## Deployment

### Docker

```sh
# Single container
docker build -t monster-game-resort-concierge .
docker run -p 8000:8000 --env-file .env monster-game-resort-concierge

# Full stack (API + Postgres + Redis + Prometheus + Grafana + MLflow)
docker-compose up --build
```

### AWS (ECS Fargate)

Deployment config in `deploy/aws/`:

* **ECS Fargate** — 1 vCPU, 2GB RAM, secrets via AWS Secrets Manager
* **ECR push:** `./deploy/aws/ecr-push.sh <account-id> <region>`
* **Deploy:** `./deploy/aws/deploy.sh <account-id> <region>`
* **CI/CD:** GitHub Actions auto-deploys on push to main (OIDC-based AWS credential assumption)

---

## Configuration

All settings via `.env` (prefix: `MRC_`). See `.env.example` for the full list.

```env
MRC_LLM_PROVIDER_PRIORITY=openai,anthropic,ollama
MRC_LLM_FALLBACK_ENABLED=true
MRC_OPENAI_MODEL=gpt-4o
MRC_HALLUCINATION_HIGH_THRESHOLD=0.7
MRC_MLFLOW_ENABLED=false
MRC_ENABLE_GRADIO=false
```

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_DATABASE_URL` | `sqlite:///./monster_resort.db` | Database connection string. Use `postgresql://user:pass@host:5432/dbname` to switch to PostgreSQL. |

SQLite is the default for local development (zero setup). For production or multi-instance deployments, set `MRC_DATABASE_URL` to a PostgreSQL connection string.

### Redis Caching

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `MRC_REDIS_ENABLED` | `false` | Set to `true` to use Redis for RAG result caching. When disabled, an in-memory TTL cache is used. |

---

## Known Limitations

- **SQLite** is the default database — set `MRC_DATABASE_URL` to a PostgreSQL connection string for multi-instance deployment
- **Hallucination detector** uses heuristic scoring (token overlap + semantic similarity), not a trained classifier — effective for high-confidence cases, less reliable in ambiguous ones
- **Cross-encoder reranking** adds ~50ms latency per query — a deliberate accuracy/latency trade-off
- **Guardrails are rule-based** — prompt injection defense and PII redaction use pattern matching, not a trained classifier
- **Knowledge base is static** — no automated ingestion pipeline for new content (manual `ingest_knowledge.py`)
- **Rate limiting is global**, not per-user — all clients share the same quota

---

## Skills Demonstrated

- **LLM application architecture** — agent loops, tool calling, conversation memory, multi-provider orchestration
- **Information retrieval** — hybrid search (BM25 + dense + RRF), cross-encoder reranking, retrieval evaluation
- **MLOps** — MLflow experiment tracking, RAGAS evaluation framework, automated benchmarking
- **Production engineering** — JWT/API key auth, input/output guardrails (injection defense, PII redaction), rate limiting, structured logging
- **Observability** — Prometheus metrics, Grafana dashboards, per-call LLM tracing with cost tracking, health/readiness separation
- **Cloud deployment** — Docker, AWS ECS Fargate, ECR, Secrets Manager, GitHub Actions CI/CD
- **Parameter-efficient fine-tuning (LoRA)** — RAG vs fine-tuned vs combined comparison with metrics
- **Testing** — 20 test files (193 tests) covering auth, guardrails, RAG, hallucination detection, LLM fallback, orchestrator, and MLOps

---

## License

MIT — see [LICENSE](LICENSE).
