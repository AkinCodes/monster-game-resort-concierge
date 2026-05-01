from __future__ import annotations
import uuid
import os
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Must come after os.environ setup
from .config import get_settings  # noqa: E402
from .database.db import DatabaseManager  # noqa: E402
from .database.cache_utils import get_cache, set_app_cache  # noqa: E402
from .core.memory import MemoryStore  # noqa: E402
from .monitoring.metrics import install_metrics  # noqa: E402
from .services.pdf_generator import PDFGenerator  # noqa: E402
from .rag.advanced_rag import AdvancedRAG  # noqa: E402
from .auth.security import install_rate_limiter, APIKeyManager  # noqa: E402
from .api.admin_routes import router as admin_router  # noqa: E402
from .auth.auth_mixins import jwt_or_api_key  # noqa: E402
from .core.tools import make_registry  # noqa: E402
from .core.llm_providers import (  # noqa: E402
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
)
from .core.observability import LLMTracer  # noqa: E402
from .core.orchestrator import ConciergeOrchestrator  # noqa: E402
from .validation.hallucination import HallucinationDetector  # noqa: E402
from .monitoring.mlflow_tracking import MLflowTracker  # noqa: E402
from .monitoring.logging_utils import setup_logging  # noqa: E402
from .validation.validators import validate_message  # noqa: E402
from .core.guardrails import InputGuard  # noqa: E402
from .core.llm_providers import ModelRouter  # noqa: E402

logger = setup_logging()


def _build_router(settings) -> ModelRouter | None:
    """Build LLM provider chain from settings."""
    providers = []
    priority = [
        p.strip() for p in settings.llm_provider_priority.split(",") if p.strip()
    ]

    for name in priority:
        if name == "openai":
            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            if api_key:
                providers.append(
                    OpenAIProvider(api_key=api_key, model=settings.openai_model)
                )
        elif name == "anthropic":
            api_key = settings.anthropic_api_key
            if api_key:
                providers.append(
                    AnthropicProvider(api_key=api_key, model=settings.anthropic_model)
                )
        elif name == "ollama":
            if settings.ollama_enabled:
                providers.append(
                    OllamaProvider(
                        base_url=settings.ollama_base_url, model=settings.ollama_model
                    )
                )

    if not providers:
        return None

    return ModelRouter(
        providers=providers, fallback_enabled=settings.llm_fallback_enabled
    )


def _init_database(settings):
    """Create database manager and API key manager."""
    db = DatabaseManager(settings)
    api_key_manager = APIKeyManager(db)
    return db, api_key_manager


def _init_cache(settings):
    """Set up application cache."""
    app_cache = get_cache(
        redis_url=settings.redis_url if settings.redis_enabled else None,
    )
    cache_type = type(app_cache).__name__
    set_app_cache(app_cache)
    logger.info(f"Cache initialized: {cache_type}")


def _init_rag(settings):
    """Build the RAG pipeline."""
    return AdvancedRAG(
        settings.rag_persist_dir,
        settings.rag_collection,
        embedding_model=getattr(settings, "embedding_model", "all-MiniLM-L6-v2"),
        reranker_model="BAAI/bge-reranker-base",
        ingestion_token=settings.rag_ingestion_token,
    )


def _init_core_services(settings, db, rag):
    """Create memory store, PDF generator, and tool registry."""
    memory = MemoryStore(db=db)
    pdf = PDFGenerator(settings.pdf_output_dir)
    registry = make_registry(
        db=db, pdf=pdf, rag_search_fn=lambda query, k=5: rag.search(query=query, k=k)
    )
    return memory, registry, pdf


def _init_llm(settings):
    """Build LLM router and tracer."""
    raw_router = _build_router(settings)
    tracer: LLMTracer | None = None
    if raw_router is not None:
        tracer = LLMTracer(raw_router)
    router = tracer
    return router, tracer


def _init_guardrails(settings):
    """Create input guard and hallucination detector."""
    input_guard = InputGuard()
    detector = HallucinationDetector(
        high_threshold=settings.hallucination_high_threshold,
        medium_threshold=settings.hallucination_medium_threshold,
    )
    return input_guard, detector


def _init_observability(app, settings):
    """Install metrics, rate limiter, and MLflow tracker."""
    install_metrics(app)
    install_rate_limiter(app, settings)
    tracker = MLflowTracker(
        tracking_uri=settings.mlflow_tracking_uri,
        experiment_name=settings.mlflow_experiment_name,
        enabled=settings.mlflow_enabled,
    )
    return tracker


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")

    db, api_key_manager = _init_database(settings)
    app.state.api_key_manager = api_key_manager

    _init_cache(settings)

    rag = _init_rag(settings)
    memory, registry, pdf = _init_core_services(settings, db, rag)
    router, tracer = _init_llm(settings)
    input_guard, detector = _init_guardrails(settings)
    tracker = _init_observability(app, settings)

    app.include_router(admin_router)

    @app.get("/health")
    def health():
        return {"ok": True, "app": settings.app_name}

    @app.get("/ready")
    def ready():
        return {"ok": True, "status": "ready"}

    @app.get("/tools")
    def list_tools():
        return {
            "ok": True,
            "tools": registry.get_openai_tool_schemas(),
        }

    orchestrator = None
    if router is not None:
        orchestrator = ConciergeOrchestrator(
            llm_provider=router,
            rag=rag,
            tool_registry=registry,
            memory_store=memory,
            detector=detector,
            input_guard=input_guard,
        )

    # --- ROUTES ---

    @app.post("/chat")
    async def chat(payload: dict, _: str = Depends(jwt_or_api_key)):
        session_id = payload.get("session_id") or str(uuid.uuid4())
        user_text = payload.get("message")

        if not user_text:
            raise HTTPException(status_code=400, detail="message is required")

        try:
            user_text = validate_message(user_text)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid message")

        if orchestrator is None:
            return {
                "ok": False,
                "reply": "AI services are offline.",
                "session_id": session_id,
            }

        result = await orchestrator.handle(user_text, session_id)

        if tracker and result.confidence:
            tracker.log_confidence_metrics(result.confidence)

        return {
            "ok": True,
            "reply": result.response,
            "session_id": session_id,
            "intent": result.plan.intent.value,
            "tools_used": (
                [result.tool_result] if result.tool_result else []
            ),
            "confidence": (
                result.confidence.to_dict()
                if result.confidence else None
            ),
            "claim_verification": (
                result.claim_verification.to_dict()
                if result.claim_verification else None
            ),
            "sources": result.sources,
            "guardrail": result.guardrail,
        }

    # --- OBSERVABILITY ENDPOINT ---

    @app.get("/api/v1/traces")
    def get_traces(limit: int = 50):
        """Return recent LLM call traces."""
        if tracer is None:
            return {"ok": True, "traces": [], "summary": {}}
        return {
            "ok": True,
            "traces": tracer.recent_traces(limit=limit),
            "summary": tracer.summary(),
        }

    # -- MCP Server --
    from .core.mcp_server import MCPServer

    mcp = MCPServer(tool_registry=registry) if registry else None

    @app.get("/api/v1/mcp/tools")
    def mcp_list_tools():
        if mcp is None:
            return {"tools": []}
        return {"tools": mcp.list_tools()}

    @app.post("/api/v1/mcp/call")
    async def mcp_call_tool(request: dict):
        if mcp is None:
            return {
                "content": [{"type": "text", "text": "MCP server not available"}],
                "isError": True,
            }
        name = request.get("name", "")
        arguments = request.get("arguments", {})
        return await mcp.call_tool(name, arguments)

    @app.get("/api/v1/mcp/info")
    def mcp_server_info():
        if mcp is None:
            return {"error": "MCP server not available"}
        return mcp.get_server_info()

    knowledge_path = Path.cwd() / "data" / "knowledge"
    if knowledge_path.exists():
        logger.info(f"Ingesting knowledge from {knowledge_path}...")
        rag.ingest_folder(str(knowledge_path), token=settings.rag_ingestion_token)

    return app


app = build_app()
