# Monster Resort Concierge - Test Suite

## 🧪 Test Suite (Updated for Multi-Model LLM, Hallucination Detection, and MLOps)

All tests have been updated to work with the new VectorRAG implementation using HuggingFace embeddings, the multi-model ModelRouter (OpenAI/Anthropic/Ollama), HallucinationDetector with confidence scoring, MLflow experiment tracking, and LangChain RAG.

## 📋 Test Files

### Core Tests
- **`conftest.py`** - Test configuration and fixtures with proper environment setup
- **`test_unit_core.py`** - Unit tests for core components (Settings, ToolRegistry, MemoryStore, VectorRAG)
- **`test_rag_unit.py`** - Unit tests for RAG functionality (ingestion, search, HuggingFace embeddings)
- **`test_ragas_eval.py`** - RAGAS evaluation tests with correct assertions

### Multi-Model and MLOps Tests
- **`test_llm_providers.py`** - Tests for ModelRouter, OpenAI/Anthropic/Ollama provider switching
- **`test_hallucination.py`** - Tests for HallucinationDetector and ConfidenceLevel scoring
- **`test_mlflow_tracking.py`** - Tests for MLflowTracker experiment logging
- **`test_langchain_rag.py`** - Tests for LangChain RAG pipeline

### API Tests
- **`test_api_basic.py`** - Basic API endpoint tests (health check)
- **`test_api_endpoints.py`** - Comprehensive API tests (chat, booking, security, confidence scores)
- **`test_booking.py`** - End-to-end booking flow tests
- **`test_rag.py`** - RAG integration tests via API

## 🔧 Setup

### 1. Install Test Dependencies

```bash
uv sync --dev
```

This installs:
- pytest
- pytest-cov
- pytest-asyncio

### 2. Set Environment Variables

Create a `.env.test` file or export:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export MRC_OPENAI_API_KEY="your-openai-api-key"  # Alternative
export MRC_ANTHROPIC_API_KEY="your-anthropic-api-key"  # For Claude provider tests
export MRC_OLLAMA_BASE_URL="http://localhost:11434"     # For local Ollama tests
export MRC_MLFLOW_TRACKING_URI="http://localhost:5000"  # For MLflow tracking tests
export MRC_HALLUCINATION_THRESHOLD="0.7"                # Confidence threshold
export TOKENIZERS_PARALLELISM=false
```

**Note:** For RAG unit tests, the OpenAI API key is not needed (uses HuggingFace embeddings). For multi-model tests (`test_llm_providers.py`), set the API key for whichever provider you want to test. MLflow tests require a running MLflow server or will use a local file store.

## 🚀 Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/test_rag_unit.py
```

### Run with Coverage
```bash
pytest --cov=app --cov-report=html
```

### Run with Verbose Output
```bash
pytest -v
```

### Run Only Fast Tests (Skip Slow Integration Tests)
```bash
pytest -m "not slow"
```

## 📊 Test Categories

### Unit Tests (Fast)
- `test_unit_core.py` - Core component tests
- `test_rag_unit.py` - RAG functionality tests
- `test_llm_providers.py` - ModelRouter and provider tests
- `test_hallucination.py` - HallucinationDetector tests
- `test_mlflow_tracking.py` - MLflowTracker tests
- `test_langchain_rag.py` - LangChain RAG pipeline tests

### Integration Tests (Medium)
- `test_api_basic.py` - Basic API tests
- `test_rag.py` - RAG integration tests

### End-to-End Tests (Slow)
- `test_api_endpoints.py` - Full API endpoint tests (includes confidence score checks)
- `test_booking.py` - Complete booking flow
- `test_ragas_eval.py` - RAGAS evaluation (requires OpenAI API)

## ✅ Key Changes from Original

### 1. **VectorRAG Instead of HybridSearch**
```python
# OLD
from app.rag import HybridSearch
rag = HybridSearch(path, collection)

# NEW
from app.rag import VectorRAG
rag = VectorRAG(path, collection)
```

### 2. **HuggingFace Embeddings (No OpenAI Key Needed for RAG)**
```python
# VectorRAG now uses sentence-transformers by default
rag = VectorRAG(path, collection)
# Uses "all-MiniLM-L6-v2" model automatically
```

### 3. **Fixed RAGAS Assertions**
```python
# OLD
assert "" in results  # ❌ Empty string check

# NEW
assert "answer_relevancy" in results  # ✅ Correct metric name
```

### 4. **Proper Test Environment Setup**
```python
# conftest.py now sets:
- OPENAI_API_KEY (for chat endpoint tests)
- TOKENIZERS_PARALLELISM=false (suppress warnings)
- MRC_RAG_PERSIST_DIR (isolated test RAG store)
```

### 5. **Multi-Model LLM Orchestration (ModelRouter replaces direct OpenAI calls)**
```python
# OLD
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(...)

# NEW
from app.llm_providers import ModelRouter
router = ModelRouter()
response = await router.chat(messages)  # Routes to OpenAI, Anthropic, or Ollama
```

### 6. **Hallucination Detection and Confidence Scores**
```python
# /chat endpoint now returns confidence scores via HallucinationDetector
from app.hallucination import HallucinationDetector, ConfidenceLevel
detector = HallucinationDetector()
# Response includes confidence: HIGH / MEDIUM / LOW
```

### 7. **MLflow Experiment Tracking**
```python
# MLflowTracker logs metrics for RAG experiments
from app.mlflow_tracking import MLflowTracker
tracker = MLflowTracker()
```

## 🎯 Expected Test Results

All tests should pass except:
- Tests requiring live OpenAI API calls (if API key not set)
- Tests requiring live Anthropic API calls (if `MRC_ANTHROPIC_API_KEY` not set)
- Tests requiring a running Ollama instance (if Ollama not installed)
- Tests requiring a running MLflow server (if `MRC_MLFLOW_TRACKING_URI` not set)
- Rate limiting tests (may need adjustment based on your rate limits)

## 🐛 Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'app.rag'`
**Solution:** Make sure you're running tests from the project root:
```bash
cd /path/to/monster-resort-concierge
pytest
```

### Issue: `APIRemovedInV1` errors
**Solution:** You're using old ChromaDB code. Make sure `app/rag.py` uses the new VectorRAG implementation.

### Issue: Tests are slow
**Solution:** Run only unit tests:
```bash
pytest tests/test_unit_core.py tests/test_rag_unit.py tests/test_llm_providers.py tests/test_hallucination.py
```

### Issue: RAGAS tests fail
**Solution:** Make sure your OpenAI API key is set and valid:
```bash
export OPENAI_API_KEY="sk-..."
pytest tests/test_ragas_eval.py
```

## 📈 Coverage Goals

- Core components: >80%
- RAG functionality: >70%
- API endpoints: >60%
- Integration tests: >50%

Run coverage report:
```bash
pytest --cov=app --cov-report=term-missing
```

## 🎊 Success Criteria

✅ All unit tests pass  
✅ RAG ingestion and search work with HuggingFace embeddings  
✅ API endpoints respond correctly  
✅ No import errors  
✅ Coverage >60% overall
