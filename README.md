<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangChain-RAG-1C3C3C?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS_ECS-FF9900?style=for-the-badge&logo=amazonaws&logoColor=white" />
</p>

# Monster Game Resort Concierge

**A production-grade AI concierge system** that serves six fictional monster-themed resort properties. Guests chat with a gothic-persona agent that retrieves answers from a 7,000+ word knowledge base using hybrid RAG, books rooms via function-calling tools, generates PDF receipts, detects hallucinations in real time, and falls back across three LLM providers automatically -- all behind JWT auth, rate limiting, and Prometheus observability.

This isn't a wrapper around an API call. It's a fully wired backend: retrieval pipeline, agent loop, tool execution, hallucination scoring, conversation memory, database persistence, and CI/CD to AWS -- built to demonstrate how these systems work together in production.

<p align="center">
  <img src="assets/chat_ui_1.png" alt="Monster Game Resort Concierge — Spa Query" width="700" />
</p>
<p align="center">
  <img src="assets/chat_ui_2.png" alt="Monster Game Resort Concierge — Hotel Listing" width="700" />
</p>

---

## What the Agent Actually Does

```
Guest: "What's the spa situation at the Mummy Resort? Asking for a friend who's been wrapped up."
Guest: "Do you have WiFi at the Ghostly B&B? I need to ghost someone on social media."
Guest: "Book me a room at Werewolf Lodge -- but not during full moon, I shed everywhere."
```

1. Message is validated, sanitized, and authenticated (JWT or API key)
2. RAG pipeline runs hybrid search -- BM25 keyword + dense vector retrieval -- fused via Reciprocal Rank Fusion, then reranked by a cross-encoder
3. Top 5 context chunks are injected into the system prompt with source attribution tags
4. LLM (OpenAI/Anthropic/Ollama) generates a response and decides to call `book_room`
5. Tool executes: validates hotel against a 6-property registry, checks dates, writes to SQLite, generates a PDF receipt
6. Tool results feed back to the LLM for a synthesis response
7. Hallucination detector scores the final output (context overlap + semantic similarity + source attribution) and assigns HIGH/MEDIUM/LOW confidence
8. Response streams back to the Gradio chat UI with confidence metadata
9. Prometheus captures request latency, token usage, RAG retrieval time, and confidence distribution

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

---

## Benchmarks & Metrics

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
| Test count | 189 tests across 18 files |
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

## Features

* **Multi-Model LLM Orchestration** — OpenAI, Anthropic, Ollama with automatic fallback (ModelRouter)
* **Hybrid RAG** — BM25 + dense embeddings + BGE cross-encoder reranker
* **Hallucination Detection** — confidence scoring on every response (HIGH/MEDIUM/LOW)
* **Function-Calling Agent** — tool registry with book_room, get_booking, search_amenities
* **MLflow MLOps** — experiment tracking, RAG evaluations, benchmark logging
* **LangChain vs Custom RAG** — head-to-head benchmarking with `scripts/benchmark_rag.py`
* **AWS Cloud Deployment** — ECS Fargate, ECR, CloudWatch, CI/CD pipeline
* **PDF Generation** — ReportLab receipts with booking confirmations
* **Prometheus + Grafana** — request latency, token usage, confidence distribution
* **JWT + API Key Auth** — bcrypt password hashing, SHA-256 key storage, rate limiting
* **Conversation Memory** — database-backed with automatic summarization at 12 messages
* **Full Test Suite** — pytest with CI/CD via GitHub Actions

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/ready` | Readiness check |
| `POST` | `/login` | Get JWT token |
| `POST` | `/chat` | Main chat endpoint (returns confidence scores + provider) |
| `POST` | `/chat/stream` | Streaming chat (SSE) |
| `GET` | `/tools` | List registered tools |
| `GET` | `/metrics` | Prometheus metrics |

---

## Authentication

### API Key

```bash
curl -H "Authorization: Bearer mr_xxx.yyy" \
  http://localhost:8000/chat \
  -d '{"message": "Book a room for Mina"}' \
  -H "Content-Type: application/json"
```

### JWT Bearer Token

```bash
# Login
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demo"}'

# Use the token
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/chat \
  -d '{"message": "Book a room for Mina"}' \
  -H "Content-Type: application/json"
```

---

## Engineering Decisions

- **SQLite with WAL mode** for efficient concurrent handling and safe multi-process access
- **SHA-256 API Key Hashing** to protect credentials and prevent plaintext storage
- **Multi-provider fallback** so the system never goes down due to a single LLM outage
- **Hybrid RAG (3-stage)** because keyword search and semantic search catch different things
- **Hallucination scoring** on every response so confidence is never hidden from the user

---

## Docker

```sh
# Single container
docker build -t monster-game-resort-concierge .
docker run -p 8000:8000 --rm monster-game-resort-concierge

# Full stack (API + Prometheus + Grafana + MLflow)
docker-compose up --build
```

---

## AWS Deployment

Full deployment config in `deploy/aws/`:

* **ECS Fargate** task definition (1 vCPU, 2GB RAM, Secrets Manager)
* **ECR push**: `./deploy/aws/ecr-push.sh <account-id> <region>`
* **Deploy**: `./deploy/aws/deploy.sh <account-id> <region>`
* **CI/CD**: GitHub Actions auto-deploys on push to main

---

## Testing

```sh
uv run pytest --cov=app
```

---

## Configuration

All settings via `.env` (prefix: `MRC_`). See `.env.example` for all options.

```env
MRC_LLM_PROVIDER_PRIORITY=openai,anthropic,ollama
MRC_LLM_FALLBACK_ENABLED=true
MRC_HALLUCINATION_HIGH_THRESHOLD=0.7
MRC_MLFLOW_ENABLED=false
MRC_ENABLE_GRADIO=false
```

---

## Project Structure

```
app/
├── main.py                 # FastAPI app, agent loop, /chat endpoint
├── config.py               # Settings from .env
├── concierge/
│   ├── tools.py            # Tool registry + book_room, get_booking, search_amenities
│   ├── memory.py           # MemoryStore — conversation persistence + summarization
│   ├── llm_providers.py    # ModelRouter — OpenAI/Anthropic/Ollama fallback
│   └── stream_client.py    # SSE streaming client
├── records_room/
│   ├── advanced_rag.py     # Hybrid RAG: BM25 + dense + RRF + cross-encoder
│   ├── langchain_rag.py    # LangChain RAG for benchmarking
│   └── rag.py              # Base RAG implementation
├── back_office/
│   └── database.py         # SQLite manager, migrations, backups
├── security_dept/
│   ├── auth.py             # JWT + API key authentication
│   └── security.py         # Rate limiting, input sanitization
├── manager_office/
│   ├── hallucination.py    # Confidence scoring (overlap + semantic + attribution)
│   └── ragas_eval.py       # RAGAS evaluation framework
├── cctv/
│   └── monitoring.py       # Prometheus metrics
├── services/
│   └── pdf_generator.py    # ReportLab PDF receipts
└── front_desk/
    └── admin_routes.py     # Admin endpoints
```

---

## Contributing

* Fork → branch → PR
* Run tests and lint before submitting
* See `pytest.ini` and `.env.example` for config
