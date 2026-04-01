# Architecture Decision Records (ADRs)

Documented decisions behind the Monster Resort Concierge system design. Each ADR follows the format: **Context → Options Considered → Decision → Trade-offs**.

---

## ADR-001: ChromaDB over Pinecone, FAISS, and Weaviate

### Context

The RAG pipeline needs a vector database to store and retrieve document embeddings. The system must support persistent storage, work locally during development, and be deployable to AWS ECS Fargate without additional managed services.

### Options Considered

| Option | Type | Strengths | Weaknesses |
|--------|------|-----------|------------|
| **ChromaDB** | Embedded, self-hosted | Zero infrastructure, persistent to disk, native Python, supports SentenceTransformer embeddings out of the box | Single-node only, no built-in multi-tenancy, limited to millions of documents |
| **Pinecone** | Managed cloud | Fully managed, scales to billions, multi-tenant, low-latency | Vendor lock-in, recurring cost, requires network calls, adds external dependency |
| **FAISS** | In-memory library | Fastest raw search, battle-tested at Meta scale | No persistence by default, no metadata filtering, requires manual serialisation |
| **Weaviate** | Self-hosted or cloud | GraphQL API, hybrid search built-in, multi-modal | Heavy infrastructure (needs its own server), overkill for single-collection use |

### Decision

**ChromaDB** — embedded persistent client with SentenceTransformer embeddings.

### Rationale

1. **Zero-infrastructure deployment** — ChromaDB runs inside the application process. No separate database server to manage, no network latency, no additional containers in the ECS task definition.
2. **Persistence without complexity** — `PersistentClient(path=persist_dir)` writes to disk automatically. No pickle serialisation (FAISS) or cloud sync (Pinecone) needed.
3. **Native embedding support** — `SentenceTransformerEmbeddingFunction` integrates directly, avoiding a separate embedding service.
4. **Cost** — $0/month. Pinecone's free tier limits to 100K vectors; ChromaDB has no limits beyond disk space.
5. **Development velocity** — Same code runs on a laptop and in production. No API keys, no network configuration, no cloud console.

### Trade-offs Accepted

- **Scale ceiling** — ChromaDB is single-node. If the knowledge base grows beyond ~5M documents or requires multi-region replication, we'd migrate to Pinecone or Weaviate.
- **No managed backups** — Persistence is local disk. In AWS ECS Fargate (ephemeral storage), the index rebuilds on cold start from the knowledge folder. For production durability, the knowledge base source files are the system of record, not the vector index.
- **No multi-tenancy** — One collection per resort chain. If we needed per-client isolation (e.g., white-labelling for multiple hotel brands), we'd need separate collections or a managed solution.

### Migration Path

If scaling beyond single-node: Pinecone (managed) or Weaviate (self-hosted on ECS). The `VectorRAG` class abstracts the storage layer — swapping ChromaDB for another provider requires changing only `__init__`, `ingest_texts`, and `search`.

---

## ADR-002: Custom Multi-Model Router over LangChain / LiteLLM

### Context

The system must call LLMs from multiple providers (OpenAI, Anthropic, Ollama) with automatic failover — if one provider is down, the system should transparently switch to the next without the caller knowing. This also needs to support tool calling (function calling) across providers with different API formats.

### Options Considered

| Option | Strengths | Weaknesses |
|--------|-----------|------------|
| **Custom ModelRouter** | Full control over failover logic, provider-specific optimisations, minimal dependencies, transparent error handling | More code to maintain, must handle API differences manually |
| **LangChain** | Large ecosystem, built-in model wrappers, community support | Heavy dependency (~50+ transitive packages), abstraction leaks on edge cases, tool calling translation is brittle across providers, slower iteration cycle |
| **LiteLLM** | Unified API across 100+ providers, drop-in OpenAI compatibility | Another external dependency, limited control over failover strategy, error handling is opaque |

### Decision

**Custom ModelRouter** with provider-specific adapters (`OpenAIProvider`, `AnthropicProvider`, `OllamaProvider`) behind a common interface.

### Rationale

1. **Failover control** — The ModelRouter tries providers in priority order (configurable via `MRC_PROVIDER_PRIORITY`). Each provider gets a clean try/except with structured error logging. LangChain and LiteLLM don't expose this level of failover control without significant workaround code.

2. **Tool calling translation** — OpenAI and Anthropic have fundamentally different tool calling formats. Our adapters handle this translation explicitly:
   - OpenAI: `tools=[{"type": "function", "function": {...}}]`
   - Anthropic: `tools=[{"name": ..., "input_schema": {...}}]`

   LangChain's tool abstraction works for simple cases but breaks on nested schemas and provider-specific features.

3. **Dependency minimalism** — The ModelRouter adds zero dependencies beyond the provider SDKs (`openai`, `anthropic`, `ollama`). LangChain would add 50+ transitive dependencies for the same functionality.

4. **Benchmarked decision** — We built a LangChain RAG implementation (`app/langchain_rag.py`) and benchmarked it against our custom implementation using MLflow. Custom outperformed on latency and gave equivalent quality, validating the decision with data.

### Trade-offs Accepted

- **More code to maintain** — ~300 lines of provider adapters vs a single LangChain import. Accepted because the code is straightforward and rarely changes.
- **No smart routing** — Current failover is linear (try provider A, then B, then C). No cost-based routing, latency-based routing, or capability-based routing. Acceptable for current scale; would add smart routing if supporting 10+ models.
- **No circuit breaker** — If provider A is consistently failing, we still try it first on every request before falling back. A circuit breaker pattern would skip known-bad providers temporarily. Not implemented because provider outages are infrequent and the failover latency (~200ms) is acceptable.

### Migration Path

If the number of providers exceeds 5 or we need advanced routing (cost optimisation, latency-based selection, A/B testing between models): evaluate LiteLLM as a routing layer while keeping our failover wrapper on top.

---

## ADR-003: Custom Hybrid RAG over Pure LangChain RAG

### Context

The concierge must answer questions about resort amenities, services, and policies using a knowledge base of text documents. Initial testing with basic vector search (dense embeddings only) showed 72% accuracy — proper nouns like "Vampire Manor" and "Castle Frankenstein" were frequently missed because embeddings encode meaning, not exact terms.

### Options Considered

| Option | Approach | Accuracy | Latency |
|--------|----------|----------|---------|
| **Basic vector search** | ChromaDB dense embeddings only | 72% | ~50ms |
| **LangChain RAG** | LangChain vectorstore + retriever chain | ~75% | ~80ms |
| **Custom Hybrid RAG** | BM25 + dense embeddings + Reciprocal Rank Fusion + BGE cross-encoder reranking | 91% | ~120ms |

### Decision

**Custom Hybrid RAG** (`AdvancedRAG` class) — three-stage retrieval pipeline.

### How It Works

```
Query → [Stage 1: Dual Retrieval]
         ├── BM25 keyword search → 20 candidates
         └── Dense embedding search → 20 candidates
       → [Stage 2: Reciprocal Rank Fusion]
         └── Merge + score: 40% BM25 weight, 60% dense weight
       → [Stage 3: Cross-Encoder Reranking (optional)]
         └── BGE reranker scores query-document pairs → top-k results
```

### Rationale

1. **Proper noun problem solved** — BM25 catches exact keyword matches ("Vampire Manor") that embeddings miss. Dense search catches semantic matches ("somewhere spooky to stay"). Combining both via Reciprocal Rank Fusion gets the best of both worlds.

2. **Measured improvement** — 72% → 91% accuracy (+26% relative improvement), validated using RAGAS evaluation framework:
   - Faithfulness: 0.88
   - Answer relevancy: 0.89
   - Context precision: 0.85

3. **Benchmarked against LangChain** — Both implementations were tested with identical queries and tracked in MLflow. Custom hybrid outperformed LangChain's retriever on proper noun queries by 40% while maintaining comparable latency.

4. **Reranking precision** — The BGE cross-encoder (`BAAI/bge-reranker-base`) scores each query-document pair directly, catching relevance that bi-encoder similarity misses. This reduced irrelevant context by 30%, which also reduced hallucinations (less noise in the LLM prompt).

### Trade-offs Accepted

- **BM25 index is in-memory** — Rebuilds on every cold start from the document corpus. Accepted because: (a) rebuild is fast (<2s for our corpus), (b) ChromaDB persists the dense index, and (c) the application is a long-running server, not a one-off script.
- **Higher latency** — ~120ms vs ~50ms for basic search. Accepted because accuracy matters more than speed for a concierge (users expect thoughtful answers, not instant ones). The 70ms difference is imperceptible in a conversational UI.
- **More dependencies** — `rank-bm25`, `sentence-transformers`, cross-encoder model. Accepted because these are well-maintained libraries and the accuracy gain justifies the dependency cost.
- **LangChain kept as benchmark** — `app/langchain_rag.py` remains in the codebase as a baseline. Not used in production, but available for future A/B testing or if LangChain's retrieval improves.

### Migration Path

If latency becomes critical (e.g., real-time autocomplete): disable cross-encoder reranking (configurable) to drop to ~70ms while keeping hybrid BM25+dense retrieval. If corpus exceeds 100K documents: evaluate ColBERT or SPLADE for more efficient hybrid retrieval.

---

## ADR-004: Real-Time Hallucination Detection over Post-Hoc Evaluation

### Context

LLMs hallucinate. In a hospitality concierge, a hallucinated room price, a fabricated spa service, or an incorrect booking policy could damage guest trust and create liability. We need a mechanism to assess response reliability before it reaches the user.

### Options Considered

| Option | Approach | Latency Impact | Accuracy |
|--------|----------|----------------|----------|
| **No detection** | Trust the LLM output | 0ms | N/A |
| **LLM-as-judge** | Send response to a second LLM for fact-checking | +500-2000ms | High but expensive |
| **SelfCheckGPT** | Sample multiple responses and check consistency | +2000-5000ms | High but very slow |
| **Custom scoring** | Token overlap + semantic similarity + source attribution | +15-30ms | Moderate, fast |

### Decision

**Custom three-factor confidence scoring** — lightweight, real-time, no additional API calls.

### Scoring Formula

```
confidence = 0.3 × context_overlap + 0.5 × semantic_similarity + 0.2 × source_attribution
```

| Factor | Weight | What It Measures |
|--------|--------|-----------------|
| Context overlap | 30% | Token-level Jaccard similarity between response and retrieved context |
| Semantic similarity | 50% | Cosine similarity using the same SentenceTransformer model as RAG |
| Source attribution | 20% | What fraction of response sentences can be grounded to a source (≥30% token overlap threshold) |

**Confidence bands:**
- **HIGH** (≥ 0.7): Response well-grounded in retrieved context
- **MEDIUM** (0.4–0.7): Partially grounded, may contain extrapolation
- **LOW** (< 0.4): Poorly grounded, likely hallucinated

### Rationale

1. **Real-time, not batch** — The confidence score is computed inline and returned with every API response. The frontend can immediately warn users on LOW confidence responses. LLM-as-judge and SelfCheckGPT are too slow for real-time use.
2. **No additional API calls** — Reuses the same embedding model already loaded for RAG. Cost per check: ~0ms compute (embeddings are cached), versus $0.01-0.03 per LLM-as-judge call.
3. **Multi-signal reduces false positives** — Token overlap alone would flag paraphrased-but-correct responses as low confidence. Semantic similarity catches paraphrasing. Source attribution catches fabricated claims. The combination is more robust than any single metric.
4. **Observable** — Confidence scores are exported as Prometheus metrics, enabling monitoring dashboards and alerting on confidence degradation over time.

### Trade-offs Accepted

- **Cannot catch subtle hallucinations** — If the LLM says "Room rates start at $199" and the context says "$299", token overlap and semantic similarity will both be high (the sentences are structurally similar). Only a fact-extraction approach would catch this. Accepted because: catching major hallucinations (fabricated services, non-existent amenities) is more valuable than catching numerical errors, and adding fact-extraction would require an additional LLM call.
- **Heuristic weights** — The 0.3/0.5/0.2 weights are based on empirical tuning, not learned. A production system could train these weights on labelled data. Accepted because the current weights produce reasonable confidence bands on our test queries.
- **No self-improvement** — The detector doesn't learn from user corrections. A feedback loop (user flags wrong answer → lower future confidence for similar queries) would improve accuracy over time but adds significant complexity.

### Migration Path

If accuracy requirements increase: add LLM-as-judge as a secondary check for MEDIUM-confidence responses only (keeping the fast heuristic as a first pass). If labelled data becomes available: train the confidence weights using logistic regression on (response, context, was_correct) triples.

---

## ADR-005: AWS ECS Fargate over EC2, EKS, and Lambda

### Context

The application needs a production deployment target. It's a long-running FastAPI server with in-memory state (BM25 index), background model loading (SentenceTransformers), and persistent connections (Prometheus scraping). It must support health checks, secret management, and centralised logging.

### Options Considered

| Option | Strengths | Weaknesses |
|--------|-----------|------------|
| **ECS Fargate** | Serverless containers, no instance management, pay-per-use, native Docker support | Cold start latency, ephemeral storage, higher per-hour cost than EC2 |
| **EC2** | Full control, persistent storage, cheapest at scale | Must manage instances, patching, scaling, AMIs |
| **EKS (Kubernetes)** | Industry standard orchestration, powerful scaling | Massive operational overhead for a single service, minimum ~$150/month for control plane |
| **Lambda** | True serverless, pay-per-invocation | 15-minute timeout, cold starts kill ML model loading, no persistent in-memory state (BM25), 10GB package limit may not fit models |

### Decision

**AWS ECS Fargate** — serverless container orchestration.

### Rationale

1. **Docker-native** — The same `Dockerfile` used in local development deploys to production. No Lambda packaging, no Kubernetes manifests, no AMI builds.
2. **Right-sized for the workload** — One service, one container, predictable traffic. EKS would be massive overkill. Lambda can't support persistent in-memory state or long model loading times.
3. **Operational simplicity** — No servers to patch, no capacity planning, no SSH access to manage. Fargate handles infrastructure entirely.
4. **Integrated ecosystem** — Native integration with CloudWatch (logging via `awslogs` driver), Secrets Manager (API keys injected as environment variables), ECR (private image registry), and ALB (load balancing).
5. **Cost-effective at low scale** — For a portfolio project with intermittent traffic, Fargate's pay-per-use model (billed per vCPU-second) is cheaper than a minimum EC2 instance running 24/7.

### Trade-offs Accepted

- **Cold start latency** — When the task starts, it must download the SentenceTransformer model and rebuild the BM25 index. First request takes 15-30 seconds. Accepted because: (a) health checks prevent traffic routing until ready, and (b) the service stays warm under normal traffic.
- **Ephemeral storage** — SQLite database and ChromaDB index don't persist across task restarts. Accepted because: (a) the knowledge base source files are the system of record, (b) the vector index rebuilds automatically, and (c) booking data in SQLite is demo-only. For production persistence, would add EFS mount or migrate to RDS.
- **No GPU support** — Fargate doesn't support GPU instances. If we needed GPU for local model inference (e.g., running Llama3 locally in production), we'd need EC2 GPU instances or SageMaker endpoints. Accepted because production uses OpenAI/Anthropic APIs, not local inference.

### Infrastructure Configuration

```
Task: 1 vCPU, 2GB RAM
Region: eu-west-2 (London)
Logging: CloudWatch via awslogs driver
Secrets: AWS Secrets Manager → environment variables
Images: ECR private registry
Deploy: ecr-push.sh → deploy.sh (register task → update service → wait stable)
```

### Migration Path

If traffic scales significantly: add Application Load Balancer + ECS auto-scaling policies (target tracking on CPU/request count). If cost becomes a concern at scale: evaluate EC2 Spot instances behind ECS. If multi-service architecture emerges: evaluate EKS, but only when managing 5+ services.

---

## Summary

| ADR | Decision | Key Driver |
|-----|----------|------------|
| 001 | ChromaDB over Pinecone/FAISS/Weaviate | Zero infrastructure, embedded persistence, cost |
| 002 | Custom ModelRouter over LangChain/LiteLLM | Failover control, tool calling translation, minimal dependencies |
| 003 | Hybrid RAG over pure vector search | 72% → 91% accuracy, proper noun handling, benchmarked with MLflow |
| 004 | Real-time hallucination scoring over LLM-as-judge | 15ms vs 2000ms latency, no additional API cost, multi-signal robustness |
| 005 | ECS Fargate over EC2/EKS/Lambda | Docker-native, operational simplicity, right-sized for workload |

Each decision was driven by **practical trade-offs**, not framework loyalty. Where possible, alternatives were benchmarked (LangChain vs custom RAG) or kept as migration paths (Pinecone, LiteLLM, EKS) for when requirements change.

---

*These ADRs document the reasoning behind architectural choices in the Monster Resort Concierge platform. They are intended for technical interviews, code reviews, and onboarding.*




 Key things that will stand out to interviewers:

  - You considered alternatives — not just "I used ChromaDB" but "I evaluated 4
  options and chose ChromaDB because..."
  - You accepted trade-offs consciously — e.g., BM25 is in-memory and rebuilds
  on cold start, and you explain why that's acceptable
  - You have migration paths — shows you think beyond the current state ("if we
  outgrow this, here's what we'd do")
  - Decisions are backed by data — the RAG decision cites the MLflow benchmark
  results

  When they ask "walk me through your architecture", point them to this file.


  Based on this project, can I apply for this job?



Dear Akin,
I hope you are doing well.
My name is Arush, and I am a Recruiter at Hays, a British multinational company providing recruitment and human resources services across 33 countries globally.
We are currently hiring for the position detailed below:
Role Details
Role Title: Solution Architect Location: London Duration: Until 31/12/2026 Days on Site: 2–3 per week Rate: £450/day (Inside IR35) Clearance: Contractor must be eligible for BPSS
Key Responsibilities
Solution Architecture & Design
* Define end-to-end GenAI solution architectures using LLMs, multimodal models, embeddings, prompt orchestration frameworks, and retrieval‐augmented generation (RAG).
* Architect scalable GenAI pipelines on cloud platforms (AWS/Azure/GCP), covering inference, fine‐tuning, model hosting, and MLOps.
* Design vector search systems using vector databases (Pinecone, FAISS, Chroma, Weaviate).
* Develop reusable architectural patterns, reference designs, and blueprints for GenAI adoption.
Technical Leadership
* Evaluate and recommend appropriate LLM models (OpenAI, Anthropic, Meta Llama, Gemini, Mistral) based on use‐case fit.
* Lead PoCs, pilots, and production rollouts for AI and automation initiatives.
* Oversee integration of GenAI with enterprise systems, APIs, microservices, and data platforms.
AI Governance, Security & Compliance
* Ensure adherence to responsible AI principles, data privacy standards, and regulatory requirements.
* Establish guardrails for safe prompting, content filtering, hallucination mitigation, and model explainability.
* Design secure access patterns for enterprise data used in RAG and model training.
Stakeholder & Delivery Management
* Translate business problems into technical solutions and clearly articulate value and ROI.
* Collaborate with product owners, SMEs, data scientists, and engineering teams to define roadmaps.

should i apply for this job???