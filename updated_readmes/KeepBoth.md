

# 🎯 **KEEP BOTH. But here's exactly why.**

They are **NOT** doing the same job. One is the **parent**, one is the **child**. `AdvancedRAG` actually **depends** on `rag.py` to work.

---

## 🔗 **THE RELATIONSHIP**

Line 23 and 28 of `advanced_rag.py` tell the whole story:

```python
from .rag import VectorRAG          # ← Imports parent from rag.py

class AdvancedRAG(VectorRAG):       # ← INHERITS from it
```

**Delete `rag.py` and `advanced_rag.py` crashes immediately.**

---

## 📊 **WHAT EACH FILE DOES**

```
rag.py (VectorRAG) — THE FOUNDATION
├── ChromaDB setup and persistence
├── Embedding model (all-MiniLM-L6-v2)
├── ingest_texts()      → Saves documents to ChromaDB
├── ingest_folder()     → Reads .txt files, calls ingest_texts
└── search()            → Dense/semantic search only

advanced_rag.py (AdvancedRAG) — THE UPGRADE
├── INHERITS everything from VectorRAG ↑
├── Adds BM25 keyword search
├── Adds Reciprocal Rank Fusion (combines BM25 + dense)
├── Adds BGE cross-encoder reranking
└── Overrides search() → Now does hybrid search
```

---

## 🏗️ **HOW THEY WORK TOGETHER**

```
User Query: "What spa services at Castle Frankenstein?"
                        │
                        ▼
              ┌─── AdvancedRAG.search() ───┐
              │                            │
              ▼                            ▼
     _bm25_search()            _dense_search()
     (keyword match)           (semantic match)
     "Castle Frankenstein"     "spa treatments"
              │                            │
              │    ← calls super().search()│
              │       which is             │
              │    VectorRAG.search()      │
              │    (from rag.py)           │
              ▼                            ▼
     ┌────────────────────────────────────┐
     │   _reciprocal_rank_fusion()        │  ← Combines both
     └────────────────────────────────────┘
                        │
                        ▼
     ┌────────────────────────────────────┐
     │         _rerank()                  │  ← Final precision
     └────────────────────────────────────┘
                        │
                        ▼
              Best results returned
```

---


