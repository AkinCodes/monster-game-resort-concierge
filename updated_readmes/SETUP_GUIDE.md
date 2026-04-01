# Advanced RAG Setup Guide

This guide walks you through upgrading your Monster Resort Concierge from Basic RAG to Advanced RAG with hybrid search and reranking.

---

## 📋 Prerequisites

- Existing Monster Resort Concierge project
- Python 3.12+
- UV package manager
- OpenAI API key (for RAGAS evaluation)
- Anthropic API key (optional, for Claude-based chat via ModelRouter)
- Ollama installed locally (optional, for local LLM inference)

---

## 🚀 Installation Steps

### Step 1: Install Dependencies

```bash
# Navigate to your project root
cd monster-resort-concierge

# Install new dependencies
uv add rank-bm25 sentence-transformers ragas datasets matplotlib seaborn pandas anthropic mlflow

# Verify installation
uv run python -c "import rank_bm25, sentence_transformers, ragas; print('✅ All dependencies installed')"
```

**Dependencies Breakdown:**
- `rank-bm25`: BM25 keyword search implementation
- `sentence-transformers`: Cross-encoder reranker models
- `ragas`: RAG evaluation framework
- `datasets`: Data handling for evaluation
- `matplotlib`, `seaborn`, `pandas`: Visualization and analysis
- `anthropic`: Anthropic Claude API client (multi-model LLM support)
- `mlflow`: MLOps experiment tracking and model metrics

---

### Step 2: Add New Files to Project

Copy the following files into your project:

```bash
# Create necessary directories
mkdir -p app notebooks docs

# Advanced RAG implementation
cp advanced_rag.py app/advanced_rag.py

# Test queries for evaluation
cp test_queries.py notebooks/test_queries.py

# Evaluation notebook
cp ragas_evaluation.ipynb notebooks/ragas_evaluation.ipynb

# Documentation
cp RAG_IMPROVEMENTS.md docs/RAG_IMPROVEMENTS.md
cp README_ADVANCED_RAG.md docs/README_ADVANCED_RAG.md
```

**File Structure:**
```
monster-resort-concierge/
├── app/
│   ├── advanced_rag.py          # Advanced RAG class
│   ├── config.py                # Centralised settings (~160 lines): Anthropic, Ollama, hallucination thresholds, MLflow
│   ├── hallucination.py         # HallucinationDetector, ConfidenceLevel
│   ├── langchain_rag.py         # LangChain RAG pipeline
│   ├── llm_providers.py         # ModelRouter, OpenAI/Anthropic/Ollama providers
│   ├── main.py                  # FastAPI app (uses `await router.chat()`)
│   ├── mlflow_tracking.py       # MLflowTracker for experiment logging
│   ├── rag.py                   # Basic VectorRAG
│   └── ...
├── deploy/
│   └── aws/                     # AWS deployment (ECS, ECR, CloudWatch, docker-compose.prod.yml)
├── scripts/
│   ├── benchmark_rag.py         # RAG benchmarking script
│   └── run_rag_experiment.py    # MLflow RAG experiments
├── notebooks/
│   ├── ragas_evaluation.ipynb   # Evaluation notebook
│   └── test_queries.py          # Gold-standard queries
├── docs/
│   ├── RAG_IMPROVEMENTS.md      # Technical docs
│   └── README_ADVANCED_RAG.md   # README section
├── general_readmes/
│   └── FEATURES_GUIDE.md        # Comprehensive features documentation
└── data/
    └── knowledge/               # Existing knowledge base
```

---

### Step 3: Update Your Main Application

**In `app/main.py`, replace the RAG initialization and LLM call:**

```python
# OLD CODE (Lines 40-45):
from .rag import VectorRAG

rag = VectorRAG(
    settings.rag_persist_dir,
    embedding_model=getattr(settings, "embedding_model", "all-MiniLM-L6-v2"),
)

# NEW CODE:
from .advanced_rag import AdvancedRAG
from .llm_providers import ModelRouter
from .hallucination import HallucinationDetector
from .mlflow_tracking import MLflowTracker

rag = AdvancedRAG(
    settings.rag_persist_dir,
    reranker_model="BAAI/bge-reranker-base"
)

# Multi-model LLM orchestration replaces direct openai.OpenAI() calls
router = ModelRouter()      # routes to OpenAI, Anthropic, or Ollama
detector = HallucinationDetector()
tracker = MLflowTracker()

# Chat endpoint now uses:
response = await router.chat(messages)  # instead of openai.OpenAI().chat(...)
```

**That's it!** The AdvancedRAG class inherits from VectorRAG, so all existing code continues to work. The ModelRouter abstracts away the choice of LLM provider.

---

### Step 4: Re-ingest Knowledge Base

The advanced system needs to build a BM25 index in addition to the vector index:

```bash
# Run the FastAPI server (it will auto-ingest)
uv run uvicorn app.main:app --reload

# Or run the ingest script manually
uv run python ingest_knowledge.py
```

**What happens:**
1. Texts are embedded with `all-MiniLM-L6-v2` (existing)
2. BM25 index is built from tokenized texts (new)
3. Both indices are cached for fast retrieval

---

### Step 5: Test the System

**Quick test via API:**

```bash
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Book Vampire Manor tonight"
  }'
```

**Expected result:**
- Hybrid search finds exact property name (BM25)
- Adds contextual information (dense embeddings)
- Reranker ensures best context is selected
- Response should be highly accurate

---

### Step 6: Run RAGAS Evaluation

**Launch Jupyter:**

```bash
cd notebooks
jupyter notebook ragas_evaluation.ipynb
```

**Run all cells:**
1. Imports and setup ✓
2. Initialize RAG systems ✓
3. Generate answers (takes ~5-10 minutes) ✓
4. Run RAGAS evaluation (takes ~3-5 minutes) ✓
5. Visualize results ✓
6. Export to JSON ✓

**Output files:**
- `docs/ragas_results.json` - Numerical results
- `docs/ragas_results.png` - Comparison chart

---

## 🔧 Configuration Options

### Tuning Hybrid Search

In `app/advanced_rag.py`, you can adjust:

```python
# BM25 weight (0-1, rest goes to dense embeddings)
rag.search(query, bm25_weight=0.4)  # Default

# Number of candidates before reranking
rag.search(query, hybrid_k=20)  # Default

# Enable/disable reranking
rag.search(query, use_reranker=True)  # Default
```

**Tuning guide:**
- `bm25_weight=0.6` → More keyword focus (proper nouns)
- `bm25_weight=0.2` → More semantic focus (concepts)
- `hybrid_k=30` → More candidates (slower but potentially better)
- `use_reranker=False` → Faster (1.4s) but less accurate (85%)

---

### Changing Reranker Model

You can use different reranker models:

```python
# Faster, less accurate
rag = AdvancedRAG(
    persist_dir,
    reranker_model="BAAI/bge-reranker-v2-m3"  # Smaller model
)

# Slower, more accurate
rag = AdvancedRAG(
    persist_dir,
    reranker_model="BAAI/bge-reranker-large"  # Larger model
)
```

**Model comparison:**
| Model | Size | Accuracy | Speed |
|-------|------|----------|-------|
| bge-reranker-base | 1.3GB | 0.85 | Medium |
| bge-reranker-v2-m3 | 800MB | 0.82 | Fast |
| bge-reranker-large | 2.1GB | 0.89 | Slow |

---

## ✅ Verification Checklist

Before running evaluation, verify:

- [ ] Dependencies installed (`uv run python -c "import rank_bm25"`)
- [ ] Files copied to correct locations
- [ ] `app/main.py` updated to use `AdvancedRAG`
- [ ] Knowledge base re-ingested
- [ ] API responds to test queries
- [ ] OpenAI API key set in environment
- [ ] Anthropic API key set (if using Claude via ModelRouter)
- [ ] MLflow server accessible (if tracking experiments)
- [ ] `app/config.py` reviewed for hallucination thresholds and provider settings

---

## 🐛 Troubleshooting

### Issue: "No module named 'rank_bm25'"

**Solution:**
```bash
uv add rank-bm25
```

---

### Issue: "BM25 index not built"

**Symptom:** Warning in logs: `"BM25 index not built, returning empty results"`

**Solution:**
```bash
# Re-run ingestion
uv run python ingest_knowledge.py
```

---

### Issue: "Reranker model not found"

**Symptom:** Error downloading `BAAI/bge-reranker-base`

**Solution:**
```bash
# Download model manually
python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"
```

---

### Issue: "RAGAS evaluation fails"

**Symptom:** `RateLimitError` from OpenAI

**Solution:**
```python
# In the notebook, add delays between queries
import time
for query in GOLD_STANDARD_QUERIES:
    result = run_rag_pipeline(rag, query)
    time.sleep(2)  # Add 2-second delay
```

---

### Issue: "Out of memory"

**Symptom:** System crashes during reranking

**Solution:**
```python
# Use smaller reranker or disable reranking
rag.search(query, use_reranker=False)
```

---

## 📊 Expected Performance

After setup, you should see:

**Latency:**
- Basic RAG: ~1.2s
- Hybrid RAG: ~1.4s
- Hybrid + Rerank: ~1.8s

**RAGAS Scores (20 test queries):**
- Faithfulness: 0.85-0.90
- Answer Relevancy: 0.85-0.92
- Context Precision: 0.80-0.88

**If your scores are significantly lower:**
1. Check if knowledge base is fully ingested
2. Verify OpenAI API key is valid
3. Review test_queries.py to ensure ground truths match your data
4. Check logs for errors during retrieval

---

## 🎯 Next Steps

- Review `general_readmes/FEATURES_GUIDE.md` for a full walkthrough of all 6 major features
- Configure multi-model routing in `app/config.py` (Anthropic, Ollama, hallucination thresholds, MLflow)
- Run MLflow experiments via `scripts/run_rag_experiment.py`
- Benchmark RAG pipelines with `scripts/benchmark_rag.py`
- Deploy to AWS using the configs in `deploy/aws/`
