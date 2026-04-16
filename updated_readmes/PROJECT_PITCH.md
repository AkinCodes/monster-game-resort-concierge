# Monster Resort Concierge — Project Pitch

How to describe this project to recruiters, hiring managers, and in interviews.

---

## The 30-Second Elevator Pitch

> "I built an **end-to-end AI concierge platform** — a production-grade FastAPI application that uses **Retrieval-Augmented Generation** to answer natural language questions about a hospitality business, handle bookings via AI tool calling, and generate invoices. What makes it stand out is that it's not a toy demo — it has **multi-model LLM failover** across OpenAI, Anthropic, and Ollama, **real-time hallucination detection** that scores every response for factual grounding, **MLflow experiment tracking**, a full **CI/CD pipeline deploying to AWS ECS Fargate**, and a comprehensive test suite with 13 test files. It's the kind of system you'd actually ship to production."

---

## The Detailed Breakdown (for technical interviews)

### What it is

An AI-powered concierge for a fictional monster-themed resort chain. Guests ask natural language questions ("What spa services does Castle Frankenstein offer?") and the system retrieves accurate answers from a knowledge base, books rooms, and generates PDF invoices — all through a conversational API.

### Why it's impressive — the 7 pillars

**1. Hybrid RAG Pipeline (not just basic vector search)**
- BM25 keyword search + dense embeddings + Reciprocal Rank Fusion + BGE cross-encoder reranking
- Improved accuracy from 72% to 91% (+26%)
- RAGAS evaluation scores: 0.88 faithfulness, 0.89 relevancy, 0.85 context precision

**2. Multi-Model LLM Orchestration**
- ModelRouter automatically fails over: OpenAI → Anthropic → Ollama (local)
- Provider-agnostic abstraction — the app doesn't know or care which model responds
- Zero-downtime resilience if any provider goes down

**3. Hallucination Detection**
- Every response is scored in real-time (HIGH/MEDIUM/LOW confidence)
- Combines context overlap (30%), semantic similarity (50%), and source attribution (20%)
- Confidence score returned to the client so the frontend can warn users

**4. Agentic AI with Tool Calling**
- OpenAI function calling for room bookings, invoice generation
- ReAct-style orchestration — the AI decides when to use tools vs. answer directly

**5. MLOps & Experiment Tracking**
- MLflow tracks RAG evaluations, model configs, confidence metrics
- Benchmarked custom RAG vs LangChain RAG side-by-side with identical queries
- Data-driven framework selection, not gut feeling

**6. Production Infrastructure**
- FastAPI async server with JWT auth, rate limiting, input validation
- SQLAlchemy ORM with switchable SQLite / PostgreSQL backends
- Redis caching layer for session and response caching
- Docker + Prometheus + Grafana monitoring stack
- docker-compose includes postgres and redis services for local and production parity
- AWS ECS Fargate deployment with ECR, CloudWatch, Secrets Manager
- CI/CD via GitHub Actions — push to main auto-deploys

**7. Comprehensive Testing**
- 13 test files covering unit, integration, and end-to-end
- Security tests (SQL injection, XSS, rate limiting)
- 28 app modules, ~28 documentation files

---

## Key Talking Points by Role

### For AI/ML Engineer roles

> "I built a hybrid RAG system from scratch, benchmarked it against LangChain, and proved custom outperforms on latency and quality. I also implemented real-time hallucination detection — not just batch evaluation."

### For Backend/Platform Engineer roles

> "It's a production FastAPI service with multi-provider LLM failover, JWT auth, rate limiting, Prometheus monitoring, and automated deployment to AWS ECS Fargate via CI/CD."

### For MLOps/ML Platform roles

> "I integrated MLflow for experiment tracking, built a RAG benchmarking framework, and set up a full observability stack — Prometheus for operational metrics, MLflow for model metrics, CloudWatch for production logs."

---

## The Numbers That Matter

| Metric | Value |
|--------|-------|
| RAG accuracy improvement | 72% → 91% (+26%) |
| Faithfulness score | 0.88 |
| App modules | 28 Python files |
| Test files | 13 |
| LLM providers supported | 3 (OpenAI, Anthropic, Ollama) |
| Monitoring services | 4 (Prometheus, Grafana, MLflow, CloudWatch) |
| Deployment | AWS ECS Fargate with CI/CD |

---

## One-Liner for LinkedIn/Resume

> **Monster Resort Concierge** — Production AI concierge platform with hybrid RAG (91% accuracy), multi-model LLM orchestration (OpenAI/Anthropic/Ollama failover), real-time hallucination detection, MLflow experiment tracking, and automated AWS ECS Fargate deployment via CI/CD.

---

## Tech Stack Summary

| Category | Technologies |
|----------|-------------|
| **Backend** | Python, FastAPI, SQLite / PostgreSQL (switchable via config), SQLAlchemy, Pydantic |
| **Caching** | Redis |
| **AI/LLM** | OpenAI GPT-4o-mini, Anthropic Claude, Ollama/Llama3 |
| **RAG** | ChromaDB, SentenceTransformers, BM25, BGE Reranker, LangChain |
| **ML/Evaluation** | RAGAS, MLflow, LoRA fine-tuning (Phi-3) |
| **Security** | JWT, bcrypt, rate limiting, input sanitisation |
| **Infrastructure** | Docker, AWS ECS Fargate, ECR, CloudWatch, Secrets Manager, PostgreSQL, Redis |
| **Monitoring** | Prometheus, Grafana, MLflow |
| **CI/CD** | GitHub Actions |
| **Testing** | pytest, 13 test files |

---

## Architecture Diagram

```
                    ┌─────────────────────────────┐
                    │        Client / API          │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │    FastAPI Application       │
                    │  (auth, rate limit, routes)  │
                    └──────────────┬──────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         │                         │                         │
         │              ┌──────────▼──────────┐              │
         │              │    Redis Cache       │              │
         │              │ (sessions/responses) │              │
         │              └──────────┬──────────┘              │
         │                         │                         │
┌────────▼────────┐ ┌──────────────▼──────────────┐ ┌────────▼──────────┐
│  ModelRouter     │ │  AdvancedRAG               │ │  Tool Registry    │
│ (OpenAI/Anthro-  │ │ (BM25+Dense+Reranking)     │ │ (book_room,       │
│  pic/Ollama)     │ │                            │ │  generate_invoice) │
└────────┬────────┘ └──────────────┬──────────────┘ └────────┬──────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │   HallucinationDetector     │
                    │  (confidence: HIGH/MED/LOW)  │
                    └──────────────┬──────────────┘
                                   │
    ┌──────────────────────────────┼──────────────────────────────┐
    │              │               │               │              │
┌───▼────────┐ ┌───▼──────────┐ ┌──▼───────────┐ ┌▼────────────┐ │
│ PostgreSQL │ │ MLflow       │ │ Prometheus   │ │ CloudWatch  │ │
│ / SQLite   │ │ Tracker      │ │ + Grafana    │ │ (prod logs) │ │
│ (SQLAlch-  │ │ (experiments)│ │              │ │             │ │
│  emy ORM)  │ │              │ │              │ │             │ │
└────────────┘ └──────────────┘ └──────────────┘ └─────────────┘ │
                                                                  │
```

---

## Target Job Roles (USA 2026)

This project directly qualifies you for the following roles:

### Tier 1 — Direct Match
| Role | Salary Range |
|------|-------------|
| **AI Engineer / LLM Engineer** | $150K--$250K |
| **RAG Developer / RAG Engineer** | $140K--$275K |
| **MLOps Engineer** | $120K--$235K |

### Tier 2 — Strong Match
| Role | Salary Range |
|------|-------------|
| **AI/ML Platform Engineer** | $140K--$250K |
| **Generative AI Developer** | $120K--$280K |
| **Backend Engineer (AI/ML Focus)** | $130K--$220K |

### Tier 3 — Stretch
| Role | Salary Range |
|------|-------------|
| **AI Solutions Architect** | $160K--$300K |
| **Machine Learning Engineer** | $140K--$250K |
| **AI Safety / AI Quality Engineer** | $130K--$200K |

**Key differentiators:** Multi-model LLM failover, hallucination detection, custom RAG vs LangChain benchmark, end-to-end production (auth, monitoring, CI/CD, AWS), MLflow integration.

---

*Generated for interview preparation and recruiter conversations.*
