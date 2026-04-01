"""
LangChain RAG Implementation
=============================

A LangChain-based RAG implementation for benchmarking against the custom
AdvancedRAG. Uses the same interface (ingest_texts, ingest_folder, search)
so results are directly comparable.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, List

from ..cctv.logging_utils import logger


class LangChainRAG:
    """LangChain-based RAG using Chroma and HuggingFace embeddings."""

    def __init__(
        self,
        persist_dir: str,
        collection: str,
        embedding_model: str = "all-MiniLM-L6-v2",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma

        self.persist_dir = persist_dir
        self.collection_name = collection
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
        self._vectorstore = Chroma(
            collection_name=collection,
            embedding_function=self._embeddings,
            persist_directory=persist_dir,
        )

        logger.info(f"LangChainRAG initialized: {collection} at {persist_dir}")

    def ingest_texts(self, texts: List[str], *, source: str = "manual") -> int:
        """Ingest texts with chunking via RecursiveCharacterTextSplitter."""
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )

        all_chunks = []
        all_metadatas = []
        all_ids = []

        for text in texts:
            chunks = splitter.split_text(text)
            for chunk in chunks:
                all_chunks.append(chunk)
                all_metadatas.append({"source": source})
                all_ids.append(str(uuid.uuid4()))

        if all_chunks:
            self._vectorstore.add_texts(
                texts=all_chunks,
                metadatas=all_metadatas,
                ids=all_ids,
            )

        logger.info(
            f"LangChainRAG ingested {len(all_chunks)} chunks from {len(texts)} texts"
        )
        return len(all_chunks)

    def ingest_folder(self, folder: str) -> int:
        """Ingest all .txt files from a folder."""
        folder_path = Path(folder)
        if not folder_path.exists():
            logger.warning(f"Folder {folder} does not exist.")
            return 0

        texts: List[str] = []
        for p in folder_path.rglob("*.txt"):
            try:
                texts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except Exception as e:
                logger.error(f"Failed to read {p}: {e}")

        if texts:
            return self.ingest_texts(texts, source=f"folder:{folder}")
        return 0

    def search(self, query: str, k: int = 5) -> dict:
        """Search and return results in the same format as VectorRAG/AdvancedRAG."""
        results = self._vectorstore.similarity_search_with_score(query, k=k)

        out = []
        for doc, score in results:
            out.append(
                {
                    "text": doc.page_content,
                    "meta": doc.metadata,
                    "score": float(score),
                }
            )

        return {"ok": True, "query": query, "results": out}


# Okay 😊 imagine you’re explaining this to a kid who likes LEGO and toy robots:
# There are two robot brains in this project 🤖🧠
# They both help the computer look up information and answer questions,
# but they’re built differently.
# 🧠 Robot Brain #1: advanced_rag.py (the big, strong one)
# This is the main robot brain. It’s the one that actually runs the app.
# It’s custom-built, like a robot you designed yourself.
# It uses two ways to search:
# One looks for matching words
# One looks for similar meaning
# It mixes the best answers together to get smarter results.
# Sometimes it double-checks answers to put the best ones on top.
# It remembers answers so it doesn’t have to think again.
# 👉 This robot brain is used:
# When people use your app
# When the server is running
# If this robot breaks, the app doesn’t work.
# 🧠 Robot Brain #2: langchain_rag.py (the practice robot)
# This one is simpler and built using a robot kit (LangChain).
# It does the same job, but in an easier, more “off-the-shelf” way
# It’s not used in the real app
# It’s just there so you can:
# Compare: “Is my robot better or faster?”
# Check: “Did I accidentally make my robot worse?”
# 👉 This robot brain is used:
# Only for tests and experiments
# Only when you’re measuring and comparing
# 🤔 Do you need both?
# To run the app: ❌ you only need the big robot (advanced_rag.py)
# To learn, compare, and test: ✅ the practice robot is helpful
# 🧹 If you clean up the toy box…
# You can throw away the practice robot 🗑️
# …but then you won’t be able to easily:
# Compare your robot to a standard one
# Catch mistakes early
# 🧠 Super simple summary
# advanced_rag.py = the real brain 🏆
# langchain_rag.py = the practice/checking brain 🧪
# Keep both if you care about learning and testing
# Keep only the first if you only care about running the app
