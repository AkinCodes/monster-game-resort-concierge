import os
from typing import Iterable
from .monitoring import Counter

RAG_HIT_COUNT = Counter("mrc_rag_hits_total", "Total RAG search hits", ["query"])

# --- Vector-based RAG using ChromaDB and HuggingFace embeddings ---
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pathlib import Path
from .logging_utils import logger, AIServiceError
from .profile_utils import profile
from .cache_utils import cache_response


class VectorRAG:
    def __init__(
        self,
        persist_dir: str,
        collection: str,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize VectorRAG with HuggingFace embeddings (compatible with ChromaDB 0.5.23).

        Args:
            persist_dir: Directory to persist ChromaDB data
            collection: Name of the collection
            embedding_model: HuggingFace model name (default: all-MiniLM-L6-v2)
        """
        self.persist_dir = persist_dir
        self.collection_name = collection
        self.embedding_model = embedding_model

        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(path=persist_dir)

        # Create or get collection with HuggingFace embeddings
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=SentenceTransformerEmbeddingFunction(
                model_name=self.embedding_model
            ),
        )

    def ingest_texts(self, texts: Iterable[str], *, source: str = "manual") -> int:
        """
        Ingest texts into the vector database.

        Args:
            texts: Iterable of text strings to ingest
            source: Source identifier for metadata // Source = sticky notes on each book

        Returns:
            Number of documents ingested


        rag = VectorRAG(persist_dir="./db", collection="Shakespeare")
        Ingest texts:
        texts = ["To be, or not to be", "All the world’s a stage"]
        rag.ingest_texts(texts, source="Hamlet")
        """
        import uuid

        metadatas = [{"source": source} for _ in texts]
        ids = [str(uuid.uuid4()) for _ in texts]

        try:
            self.collection.add(documents=list(texts), metadatas=metadatas, ids=ids)
            return len(ids)
        except Exception as e:
            logger.error(f"ChromaDB ingestion failed: {e}")
            raise AIServiceError(f"ChromaDB ingestion failed: {e}")

    def ingest_folder(self, folder: str) -> int:
        """
        Ingest all .txt files from a folder into the vector database.

        Args:
            folder: Path to folder containing .txt files

        Returns:
            Number of documents ingested
        """
        folder_path = Path(folder)
        if not folder_path.exists():
            logger.warning(f"Knowledge folder not found: {folder}")
            return 0

        texts: list[str] = []
        for p in folder_path.rglob("*.txt"):
            try:
                texts.append(p.read_text(encoding="utf-8", errors="ignore"))
            except Exception as e:
                logger.error(f"Failed to read file {p}: {e}")
                raise AIServiceError(f"Failed to read file {p}: {e}")

        try:
            return self.ingest_texts(texts, source=f"folder:{folder}")
        except Exception as e:
            logger.error(f"Failed to ingest texts from folder {folder}: {e}")
            raise AIServiceError(f"Failed to ingest texts from folder {folder}: {e}")

    @profile
    @cache_response(ttl=300)
    def search(self, query: str, k: int = 5) -> dict:
        """
        Search the vector database for relevant documents.

        Args:
            query: Search query string
            k: Number of results to return

        Returns:
            Dictionary with search results
        """
        try:
            results = self.collection.query(query_texts=[query], n_results=k)
            docs = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            scores = results.get("distances", [[]])[0]

            out = [
                {"text": doc, "meta": meta, "score": float(score)}
                for doc, meta, score in zip(docs, metadatas, scores)
            ]

            if out:
                RAG_HIT_COUNT.labels(query=query).inc()

            return {"ok": True, "query": query, "results": out}
        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            raise AIServiceError(f"ChromaDB search failed: {e}")


# 1. Library and Dewey Decimal
# ChromaDB = library shelves
# Embeddings = book topics converted into numbers
# RAG = finding the right book to answer your question
# Analogy: You ask the librarian (RAG) a question. They look up the
# book number (embedding) in the shelves (ChromaDB) and give you the right book.


# ingest_texts ---- so lets say we have ["AI is cool", "Cats are fluffy"] from document_1 and
# ["AI is not cool", "Dogs are loud"] from document_2. so are you saying for
# each piece of text in these docs, they all each get metadata and labels.


# sematic search
# Great question — this phrase sounds fancy but the idea is actually **very simple**.

# **“It does semantic search”** means:

# > **It searches by meaning, not just by matching exact words.**

# Now here are **10 very simple analogies** to lock that in 👇

# ---

# ### 1. **Smart Librarian**

# You ask, “Books about space travel.”
# The librarian gives you books about rockets and astronauts — even if the word *“space travel”* isn’t in the title.

# ---

# ### 2. **Talking to a Human**

# You say, “I’m feeling down.”
# Your friend understands you’re sad — even though you didn’t say the word *“sad.”*

# ---

# ### 3. **Google Maps**

# You type “coffee nearby.”
# It shows cafés — not just places with the word *“coffee”* in their name.

# ---

# ### 4. **Movie Recommendations**

# You say, “I want something funny.”
# It suggests comedies — not movies with the word *“funny”* in the title.

# ---

# ### 5. **Teacher Grading an Essay**

# You explain an idea in your own words.
# The teacher understands you got the concept — even if you didn’t use the textbook wording.

# ---

# ### 6. **Emoji Understanding**

# You send 😡
# Your friend knows you’re angry — you didn’t type the word “angry”.

# ---

# ### 7. **Shopping Assistant**

# You say, “Something warm for winter.”
# The assistant shows coats and sweaters — not items literally labeled “warm”.

# ---

# ### 8. **Lost & Found Description**

# You say, “I lost a small black wallet.”
# They find it even if the tag says “leather card holder”.

# ---

# ### 9. **Music Search**

# You say, “Chill music for studying.”
# It plays lo-fi and soft beats — not songs with “study” in the lyrics.

# ---

# ### 10. **Talking to a Child**

# You say, “Don’t touch that, it’s hot.”
# The child understands “hot” means “it will hurt me,” not just “high temperature.”

# ---

# ## Super short takeaway 🧠

# > **Semantic search understands meaning, not just words.**

# Or even shorter:

# > **It searches like a human, not like Ctrl+F.**

# If you want, I can also explain:

# * semantic search vs keyword search (side-by-side)
# * how embeddings make semantic search possible


# 2️⃣ Analogy for your example
# If you want to store all the works of Shakespeare in ChromaDB:
# collection = "Shakespeare"
# This creates one collection (bookshelf/folder) in ChromaDB called "Shakespeare".
# All the texts you ingest (e.g., “Hamlet,” “Macbeth”) go into this one collection.
# ✅ You could later have other collections like "Shakespeare_Quotes" or "Modern_Poetry".
# Each collection is independent.
# 3️⃣ How this works with the class
# class VectorRAG:
#     def __init__(
#         self,
#         persist_dir: str,
#         collection: str,
#         embedding_model: str = "all-MiniLM-L6-v2",
#     ):
# persist_dir → folder on disk to save the database permanently
# collection → the single “shelf” where your texts live
# embedding_model → Hugging Face model used to convert texts into embeddings (numbers)
# So when you call:
# rag = VectorRAG(persist_dir="./db", collection="Shakespeare")
# It will store all Shakespeare texts in one collection called "Shakespeare"
# The data lives on disk in ./db, so it persists after you close the program.
