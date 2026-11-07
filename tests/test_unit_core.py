import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.config import Settings
from app.core.tools import make_registry
from app.core.memory import MemoryStore
from app.services.pdf_generator import PDFGenerator
from app.rag.vector_rag import VectorRAG
from app.database.db import DatabaseManager, ordered_ddl


def test_settings_load():
    """Test that settings load correctly."""
    s = Settings()
    assert s.app_name
    assert s.database_url
    assert s.rag_collection


def test_tool_registry():
    """Test tool registry initialization and basic operations."""
    db = DatabaseManager(Settings())
    pdf = PDFGenerator("./test_pdfs")
    rag = VectorRAG("./.rag_store", "test_collection")

    reg = make_registry(
        db=db, pdf=pdf,
        rag_search_fn=lambda q, k=5: rag.search(q, k)
    )
    tools = reg.list()

    assert len(tools) > 0
    assert reg.get(tools[0].name)


def test_memory_store():
    """Test memory store initialization."""
    db = DatabaseManager(Settings())
    mem = MemoryStore(db=db)
    assert mem is not None


def test_memory_returns_latest_messages_in_order():
    """Test get_messages returns the most recent messages, oldest first."""
    mem = MemoryStore(db=DatabaseManager(Settings()))
    for i in range(7):
        mem.add_message("latest-session", "user", f"message {i}")

    contents = [m["content"] for m in mem.get_messages("latest-session", limit=5)]

    assert contents == [f"message {i}" for i in range(2, 7)]


def test_memory_keeps_summary_after_clearing(monkeypatch):
    """Test the history is cleared at the threshold and the summary is kept."""
    monkeypatch.setitem(sys.modules, "openai", None)
    mem = MemoryStore(db=DatabaseManager(Settings()))
    for i in range(12):
        mem.add_message("summary-session", "user", f"Please book Vampire Manor {i}")

    summary = mem.get_summary("summary-session")

    assert mem.get_messages("summary-session") == []
    assert "booking" in summary
    assert "Vampire Manor" in summary


def test_memory_uses_llm_summary_with_prefixed_key(monkeypatch):
    """Test the LLM summary runs when only MRC_OPENAI_API_KEY is set."""
    reply = SimpleNamespace(content="Guest asked to book Vampire Manor")
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=reply)]
    )
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda api_key: client))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("MRC_OPENAI_API_KEY", "sk-test")
    mem = MemoryStore(db=DatabaseManager(Settings()))
    for i in range(12):
        mem.add_message("llm-summary-session", "user", f"Please book Vampire Manor {i}")

    assert mem.get_summary("llm-summary-session") == "Guest asked to book Vampire Manor"


@pytest.mark.parametrize("is_postgres", [True, False])
def test_tables_are_created_after_sessions(is_postgres):
    """Test every table that references sessions is created after it (Postgres requires this)."""
    ddl = ordered_ddl(is_postgres)

    def position(table):
        return next(i for i, s in enumerate(ddl) if f"TABLE IF NOT EXISTS {table} " in s)

    for table in ("messages", "bookings", "turn_metadata"):
        assert position("sessions") < position(table)
    assert all("CREATE INDEX" in s for s in ddl[5:])


def test_vector_rag_initialization():
    """Test VectorRAG initializes correctly with HuggingFace embeddings."""
    rag = VectorRAG("./.rag_store_test", "test_collection")
    assert rag is not None
    assert rag.collection_name == "test_collection"
    assert rag.embedding_model == "all-MiniLM-L6-v2"  # Default model
