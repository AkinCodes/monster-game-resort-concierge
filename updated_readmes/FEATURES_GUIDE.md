# Monster Resort Concierge — Features Guide

A comprehensive guide to the 6 production features added to the Monster Resort Concierge platform.

---

## Table of Contents

1. [Multi-Model LLM Orchestration](#1-multi-model-llm-orchestration)
2. [Hallucination Mitigation](#2-hallucination-mitigation)
3. [MLflow MLOps Platform](#3-mlflow-mlops-platform)
4. [LangChain vs Custom RAG Evaluation](#4-langchain-vs-custom-rag-evaluation)
5. [AWS Cloud Deployment](#5-aws-cloud-deployment)
6. [Environment Variable Reference](#6-environment-variable-reference)

---

## 1. Multi-Model LLM Orchestration

**File:** `app/llm_providers.py`
**Tests:** `tests/test_llm_providers.py`

### What It Does

Provides a unified interface for multiple LLM providers (OpenAI, Anthropic, Ollama) with automatic fallback routing. The rest of the application is provider-agnostic — it sends normalised `LLMMessage` objects and receives normalised `LLMResponse` objects regardless of which provider handles the request.

### Architecture

```
User Request
    │
    ▼
┌─────────────┐
│ ModelRouter  │  ← tries providers in priority order
├─────────────┤
│ Provider 1  │──► OpenAI   (gpt-4o-mini)
│ Provider 2  │──► Anthropic (claude-sonnet)
│ Provider 3  │──► Ollama   (llama3, local)
└─────────────┘
    │
    ▼
Normalised LLMResponse
```

### Key Classes

| Class | Purpose |
|-------|---------|
| `LLMMessage` | Normalised message (role, content, tool_calls, tool_call_id) |
| `LLMResponse` | Normalised response (content, tool_calls, model, provider, usage) |
| `LLMProvider` | Abstract base class — implement `chat()` and `name` |
| `OpenAIProvider` | Wraps `openai.AsyncOpenAI`, tool schemas are native |
| `AnthropicProvider` | Wraps `anthropic.AsyncAnthropic`, translates tool schemas |
| `OllamaProvider` | Uses `httpx.AsyncClient` to POST to local Ollama server |
| `ModelRouter` | Ordered list of providers with fallback on failure |

### Configuration

```bash
# Provider priority (comma-separated, tried left-to-right)
MRC_LLM_PROVIDER_PRIORITY=openai,anthropic,ollama

# Enable automatic fallback to next provider on failure
MRC_LLM_FALLBACK_ENABLED=true

# Anthropic settings
MRC_ANTHROPIC_API_KEY=sk-ant-...
MRC_ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Ollama settings (local models)
MRC_OLLAMA_BASE_URL=http://localhost:11434
MRC_OLLAMA_MODEL=llama3
MRC_OLLAMA_ENABLED=false
```

### How Fallback Works

1. Router tries the first provider in the priority list.
2. If it raises an exception, the router catches it, logs the failure, and moves to the next provider.
3. If all providers fail, the last exception is raised.
4. The `provider` field in the response tells you which provider succeeded.

### Running Tests

```bash
pytest tests/test_llm_providers.py -v
```

---

## 2. Hallucination Mitigation

**File:** `app/hallucination.py`
**Tests:** `tests/test_hallucination.py`

### What It Does

Scores every LLM response against the RAG contexts that were provided, producing a confidence score that indicates how well the response is grounded in the knowledge base. This helps detect potential hallucinations.

### Scoring Method

The confidence score is a weighted combination of three signals:

| Signal | Weight | How It Works |
|--------|--------|-------------|
| Context Overlap | 30% | Token-level intersection between response and RAG contexts |
| Semantic Similarity | 50% | Cosine similarity using sentence-transformer embeddings |
| Source Attribution | 20% | Sentence-level check — what fraction of response sentences have a matching source |

### Confidence Levels

| Level | Threshold | Meaning |
|-------|-----------|---------|
| HIGH | ≥ 0.7 | Response is well-grounded in the knowledge base |
| MEDIUM | ≥ 0.4 | Partially grounded — may contain some unsupported claims |
| LOW | < 0.4 | Likely hallucination — response has weak connection to sources |

### API Response

Every `/chat` response now includes a `confidence` field:

```json
{
  "ok": true,
  "reply": "The Crimson Wing suite overlooks...",
  "confidence": {
    "overall_score": 0.82,
    "level": "HIGH",
    "context_overlap_score": 0.75,
    "semantic_similarity_score": 0.88,
    "source_attribution_score": 0.79
  },
  "provider": "openai"
}
```

### Configuration

```bash
MRC_HALLUCINATION_HIGH_THRESHOLD=0.7
MRC_HALLUCINATION_MEDIUM_THRESHOLD=0.4
```

### Running Tests

```bash
pytest tests/test_hallucination.py -v
```

---

## 3. MLflow MLOps Platform

**File:** `app/mlflow_tracking.py`
**Tests:** `tests/test_mlflow_tracking.py`
**Script:** `scripts/run_rag_experiment.py`

### What It Does

Provides experiment tracking for RAG evaluations, model configurations, confidence metrics, and benchmark results. Integrates with the MLflow UI for visual comparison of experiments. Gracefully degrades to a no-op when MLflow is not installed or the server is unreachable.

### Architecture

```
App / Scripts
    │
    ▼
┌──────────────────┐
│  MLflowTracker   │  ← wraps mlflow API calls
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  MLflow Server   │  ← http://localhost:5000
│  (Docker)        │
│  SQLite backend  │
│  Local artifacts │
└──────────────────┘
```

### Key Methods

| Method | What It Logs |
|--------|-------------|
| `log_rag_evaluation()` | Query, results, scores, latency |
| `log_model_config()` | Provider settings, model names, thresholds |
| `log_confidence_metrics()` | Per-request confidence scores and levels |
| `log_benchmark_results()` | Custom vs LangChain RAG comparison data |

### Running MLflow Locally

```bash
# Start via Docker Compose (includes MLflow service)
docker-compose up -d mlflow

# MLflow UI available at http://localhost:5000
```

### Running RAG Experiments

```bash
# Enable MLflow tracking
export MRC_MLFLOW_ENABLED=true
export MRC_MLFLOW_TRACKING_URI=http://localhost:5000

# Run the experiment script
python scripts/run_rag_experiment.py
```

### Configuration

```bash
MRC_MLFLOW_TRACKING_URI=http://localhost:5000
MRC_MLFLOW_EXPERIMENT_NAME=monster-resort-concierge
MRC_MLFLOW_ENABLED=false  # set to true to enable
```

### Running Tests

```bash
pytest tests/test_mlflow_tracking.py -v
```

---

## 4. LangChain vs Custom RAG Evaluation

**File:** `app/langchain_rag.py`
**Tests:** `tests/test_langchain_rag.py`
**Script:** `scripts/benchmark_rag.py`

### What It Does

Implements a LangChain-based RAG system with the same interface as the custom `AdvancedRAG`, allowing direct performance and quality comparison. The benchmark script ingests the same knowledge base into both systems, runs identical queries, and compares latency and result quality.

### Comparison

| Aspect | Custom AdvancedRAG | LangChain RAG |
|--------|-------------------|---------------|
| Vector Store | ChromaDB (direct) | Chroma via LangChain |
| Embeddings | SentenceTransformer | HuggingFaceEmbeddings |
| Reranking | BGE Reranker | Not included |
| Chunking | Custom splitter | RecursiveCharacterTextSplitter |
| Hybrid Search | BM25 + vector | Vector only |

### Running the Benchmark

```bash
# Basic run (prints comparison table)
python scripts/benchmark_rag.py

# With MLflow logging
MRC_MLFLOW_ENABLED=true python scripts/benchmark_rag.py
```

### Sample Output

```
╔══════════════════════════════════════════════════════════════╗
║               RAG Benchmark Results                         ║
╠══════════════════╦══════════════╦══════════════╦════════════╣
║ Query            ║ Custom (ms)  ║ LangChain(ms)║ Quality    ║
╠══════════════════╬══════════════╬══════════════╬════════════╣
║ Room amenities   ║ 12.3         ║ 15.7         ║ Custom+    ║
║ Dining options   ║ 11.8         ║ 14.2         ║ Tie        ║
╚══════════════════╩══════════════╩══════════════╩════════════╝
```

### Running Tests

```bash
pytest tests/test_langchain_rag.py -v
```

---

## 5. AWS Cloud Deployment

**Directory:** `deploy/aws/`
**CI Workflow:** `.github/workflows/ci.yml`

### What It Does

Provides everything needed to deploy the Monster Resort Concierge to AWS using ECS Fargate, ECR for container images, Secrets Manager for credentials, and CloudWatch for logging.

### Files

| File | Purpose |
|------|---------|
| `ecs-task-definition.json` | Fargate task definition (1 vCPU, 2GB RAM, health checks, secrets) |
| `ecr-push.sh` | Build and push Docker image to Amazon ECR |
| `deploy.sh` | Register task definition and update ECS service |
| `cloudwatch-log-group.json` | CloudWatch log group with 30-day retention |
| `docker-compose.prod.yml` | Production compose with awslogs driver and resource limits |

### Architecture

```
GitHub Actions (CI/CD)
    │
    ├──► Build & Push to ECR
    │
    └──► Deploy to ECS Fargate
              │
              ▼
    ┌─────────────────┐
    │  ECS Fargate     │
    │  ┌─────────────┐ │
    │  │ API (8000)  │ │ ◄── Secrets Manager (API keys)
    │  └─────────────┘ │
    │         │         │
    │         ▼         │
    │  CloudWatch Logs  │
    └─────────────────┘
```

### Prerequisites

Before deploying, set up these AWS resources:

1. **ECR Repository** — created automatically by `ecr-push.sh`
2. **ECS Cluster** — create via AWS console or CLI
3. **IAM Roles** — `ecsTaskExecutionRole` (with Secrets Manager access) and `ecsTaskRole`
4. **Secrets Manager** — store your API keys:
   ```bash
   aws secretsmanager create-secret --name monster-resort/openai-api-key --secret-string "sk-..."
   aws secretsmanager create-secret --name monster-resort/api-key --secret-string "your-api-key"
   aws secretsmanager create-secret --name monster-resort/anthropic-api-key --secret-string "sk-ant-..."
   ```
5. **CloudWatch Log Group**:
   ```bash
   aws logs create-log-group --log-group-name /ecs/monster-resort-concierge
   aws logs put-retention-policy --log-group-name /ecs/monster-resort-concierge --retention-in-days 30
   ```

### Manual Deployment

```bash
# Step 1: Push image to ECR
./deploy/aws/ecr-push.sh 123456789012 eu-west-2 v1.0.0

# Step 2: Deploy to ECS
./deploy/aws/deploy.sh 123456789012 eu-west-2 monster-resort monster-resort-api
```

### CI/CD (Automatic)

The `.github/workflows/ci.yml` workflow now includes a `deploy` job that runs automatically on pushes to `main` after tests pass. It requires these GitHub repository secrets:

| Secret | Description |
|--------|-------------|
| `AWS_ROLE_ARN` | IAM role ARN for OIDC authentication |
| `AWS_REGION` | AWS region (e.g. `eu-west-2`) |
| `AWS_ACCOUNT_ID` | AWS account ID |
| `ECS_CLUSTER` | ECS cluster name |
| `ECS_SERVICE` | ECS service name |

### Production Docker Compose

For EC2-based deployments (instead of Fargate):

```bash
docker-compose -f deploy/aws/docker-compose.prod.yml up -d
```

This includes resource limits, awslogs driver, and health checks.

---

## 6. Environment Variable Reference

All settings use the `MRC_` prefix. Set them in `.env` or as environment variables.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_ENVIRONMENT` | `dev` | `dev`, `staging`, `prod` |
| `MRC_HOST` | `0.0.0.0` | Server bind host |
| `MRC_PORT` | `8000` | Server bind port |
| `MRC_LOG_LEVEL` | `info` | Logging level |
| `MRC_DATABASE_URL` | `sqlite:///./monster_resort.db` | Database connection string |
| `MRC_API_KEY` | (auto-generated) | API authentication key |
| `MRC_RATE_LIMIT_PER_MINUTE` | `60` | Rate limit per API key |

### LLM Providers

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_OPENAI_API_KEY` | `None` | OpenAI API key |
| `MRC_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model |
| `MRC_ANTHROPIC_API_KEY` | `None` | Anthropic API key |
| `MRC_ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model |
| `MRC_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `MRC_OLLAMA_MODEL` | `llama3` | Ollama model name |
| `MRC_OLLAMA_ENABLED` | `false` | Enable Ollama provider |
| `MRC_LLM_PROVIDER_PRIORITY` | `openai` | Comma-separated provider order |
| `MRC_LLM_FALLBACK_ENABLED` | `true` | Auto-fallback on provider failure |

### Hallucination Detection

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_HALLUCINATION_HIGH_THRESHOLD` | `0.7` | Score ≥ this = HIGH confidence |
| `MRC_HALLUCINATION_MEDIUM_THRESHOLD` | `0.4` | Score ≥ this = MEDIUM confidence |

### MLflow

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_MLFLOW_TRACKING_URI` | `http://localhost:5000` | MLflow server URL |
| `MRC_MLFLOW_EXPERIMENT_NAME` | `monster-resort-concierge` | Experiment name |
| `MRC_MLFLOW_ENABLED` | `false` | Enable MLflow tracking |

### RAG

| Variable | Default | Description |
|----------|---------|-------------|
| `MRC_RAG_COLLECTION` | `monster_resort_knowledge` | ChromaDB collection name |
| `MRC_RAG_PERSIST_DIR` | `./.rag_store` | RAG storage directory |
| `MRC_RAG_MAX_RESULTS` | `5` | Max RAG results per query |

---

## Quick Start — Running Everything Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
export MRC_OPENAI_API_KEY=sk-...

# 3. Run the app
uvicorn app.main:app --reload

# 4. Start supporting services (Prometheus, Grafana, MLflow)
docker-compose up -d

# 5. Run all tests
pytest --cov=app -v

# 6. Run the RAG benchmark
python scripts/benchmark_rag.py

# 7. Run RAG experiments with MLflow
MRC_MLFLOW_ENABLED=true python scripts/run_rag_experiment.py
# Then visit http://localhost:5000 to view results
```

---

## Troubleshooting

### "AI services are offline"
No LLM provider could be initialised. Check that at least one API key is set (`MRC_OPENAI_API_KEY` or `MRC_ANTHROPIC_API_KEY`) or enable Ollama.

### MLflow not logging
Ensure `MRC_MLFLOW_ENABLED=true` and the MLflow server is running (`docker-compose up -d mlflow`). The tracker gracefully degrades to a no-op if the server is unreachable.

### Ollama connection refused
Start the Ollama server locally (`ollama serve`) and ensure `MRC_OLLAMA_ENABLED=true`. Check the URL matches `MRC_OLLAMA_BASE_URL`.

### Low confidence scores
Low scores don't necessarily mean the response is wrong — they indicate weak grounding in the RAG knowledge base. If the query is about something not in the knowledge base, low scores are expected. Ingest more relevant documents to improve coverage.

### ECS deployment fails
- Verify IAM roles have the correct permissions (Secrets Manager read, ECR pull, CloudWatch write).
- Check that all secrets exist in AWS Secrets Manager.
- Review CloudWatch logs at `/ecs/monster-resort-concierge` for container errors.
