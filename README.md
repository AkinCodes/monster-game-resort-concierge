# Monster Resort Concierge

An AI-powered concierge system for a fictional monster-themed resort chain. Guests interact with a conversational agent that handles bookings, answers questions about six unique monster properties, generates PDF receipts, and streams real-time responses -- all backed by retrieval-augmented generation over a custom knowledge base.

Built as a production-grade backend project to demonstrate real-world AI/ML engineering patterns: RAG pipelines, multi-provider LLM routing, hallucination detection, tool-calling agents, and observability -- deployed via Docker on AWS ECS.

---

## Architecture

```
Client (Gradio Chat UI)
       |
   FastAPI Server
       |
  +----+----+----+----+----+
  |         |         |         |
Auth &    LLM       RAG      Tools
Rate     Router   Pipeline   (Booking,
Limit   (OpenAI,  (LangChain  PDF,
(JWT,   Anthropic, + ChromaDB) Memory)
API Key) Ollama)
  |         |         |         |
  +----+----+----+----+----+
       |
  +----+----+
  |         |
SQLite   Prometheus
(Bookings, (Metrics &
 Users)   Monitoring)
```

## Key Features

**Retrieval-Augmented Generation (RAG)**
- Hybrid search: semantic vector retrieval (ChromaDB + HuggingFace embeddings) combined with BM25 keyword matching
- Custom knowledge base covering 6 monster resort properties -- amenities, policies, seasonal events, and FAQs
- RAGAS evaluation framework for measuring retrieval quality (faithfulness, relevance, recall)
- RAG ingestion security with token-gated endpoints

**Multi-Provider LLM Routing**
- Configurable priority chain across OpenAI, Anthropic, and Ollama (local)
- Automatic fallback: if the primary provider fails, requests route to the next available provider
- Consistent interface via `ModelRouter` abstraction -- swap providers without changing application code

**Tool-Calling Agent**
- Function-calling loop: the LLM can invoke tools (book rooms, check availability, generate receipts) and reason over results
- Booking system with date validation, conflict detection, and room management across all properties
- PDF receipt generation with guest details, stay summary, and pricing

**Hallucination Detection**
- Scores every response against retrieved context using semantic similarity
- Flags high/medium/low confidence with configurable thresholds
- Logged per-request for monitoring and evaluation

**Observability & Monitoring**
- Prometheus metrics: request latency, LLM call duration, RAG retrieval times, error rates
- MLflow experiment tracking for RAG configuration experiments
- Structured logging with correlation IDs

**Security**
- JWT authentication + API key management
- Rate limiting per endpoint (SlowAPI)
- Input sanitization (bleach) and validation (Pydantic)
- Non-root Docker user, health checks, environment-based config

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI, Pydantic, Uvicorn |
| LLM Providers | OpenAI, Anthropic, Ollama |
| RAG | LangChain, ChromaDB, HuggingFace Embeddings, BM25 |
| RAG Evaluation | RAGAS |
| Database | SQLAlchemy + SQLite (Alembic migrations) |
| Auth | JWT (PyJWT), bcrypt, API key management |
| Monitoring | Prometheus, MLflow |
| UI | Gradio |
| Deployment | Docker, AWS ECS, ECR, GitHub Actions CI/CD |
| Testing | pytest, pytest-cov, pytest-asyncio |

## Project Structure

```
app/
  main.py              # FastAPI app, chat endpoint, tool-calling loop
  config.py            # Pydantic settings (env-driven configuration)
  llm_providers.py     # Multi-provider LLM router (OpenAI, Anthropic, Ollama)
  advanced_rag.py      # Hybrid RAG pipeline (vector + BM25)
  langchain_rag.py     # LangChain RAG integration
  hallucination.py     # Hallucination detection scoring
  tools.py             # Tool registry (booking, availability, receipts)
  database.py          # SQLAlchemy models and database manager
  auth.py              # JWT token creation and verification
  security.py          # Rate limiting, API key management
  monitoring.py        # Prometheus metrics instrumentation
  mlflow_tracking.py   # MLflow experiment tracking
  pdf_generator.py     # PDF receipt generation
  validation.py        # Input validation and sanitization

data/
  knowledge/           # Monster resort knowledge base (6 properties)
  concierge_qa.json    # QA pairs for fine-tuning and evaluation

scripts/
  benchmark_rag.py     # RAG performance benchmarking
  finetune_lora.py     # LoRA fine-tuning script
  run_rag_experiment.py

tests/                 # Unit and integration tests
notebooks/             # RAG evaluation and experimentation notebooks
deploy/aws/            # ECS task definitions, deploy scripts
```

## Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Setup

```bash
# Clone the repo
git clone https://github.com/AkinCodes/monster-resort-concierge.git
cd monster-resort-concierge

# Create environment and install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys (OpenAI, Anthropic, or run locally with Ollama)

# Ingest the knowledge base into ChromaDB
python inspect_and_ingest_rag.py

# Run the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` and the Gradio chat UI at `http://localhost:8000/chat`.

### Docker

```bash
docker compose up --build
```

### Running Tests

```bash
pytest --cov=app --cov-report=term-missing
```

## How It Works

1. A guest sends a message through the Gradio chat UI
2. The message is validated, sanitized, and authenticated
3. The RAG pipeline retrieves relevant context from the monster resort knowledge base
4. The LLM generates a response using retrieved context + conversation memory
5. The hallucination detector scores the response against source documents
6. If the LLM invokes a tool (e.g., book a room), the tool executes and results feed back into the conversation
7. The response streams back to the client in real time
8. Prometheus captures latency, token usage, and retrieval metrics throughout

## CI/CD

GitHub Actions pipeline runs on every push to `main`:
- Linting (flake8)
- Test suite with coverage
- Docker build, push to ECR, and deploy to ECS (production)

## License

This project is for portfolio and educational purposes.
