from __future__ import annotations
import uuid
import os
import json
from datetime import datetime
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Must come after os.environ setup
from .monitoring.profile_utils import profile  # noqa: E402
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
from .core.tools import make_registry, VALID_HOTELS  # noqa: E402
from .core.llm_providers import (  # noqa: E402
    ModelRouter,
    LLMMessage,
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
from .core.guardrails import InputGuard, OutputGuard  # noqa: E402

logger = setup_logging()


def _validate_tool_call(tool_name: str, tool_args: dict) -> tuple[bool, str]:
    """Defense 6: Validate tool call arguments against authoritative registries."""
    if tool_name == "book_room":
        hotel = tool_args.get("hotel_name", "")
        if hotel not in VALID_HOTELS:
            return False, f"Blocked: unknown hotel '{hotel}'. Not in official registry."
    elif tool_name == "get_booking":
        booking_id = tool_args.get("booking_id", "")
        if not booking_id or not booking_id.strip():
            return False, "Blocked: booking_id cannot be empty."
    elif tool_name == "search_amenities":
        query = tool_args.get("query", "")
        if not query or not query.strip():
            return False, "Blocked: search query cannot be empty."
        if len(query) > 500:
            return False, "Blocked: search query exceeds 500 character limit."
    else:
        logger.warning("validate_tool_call_unknown_tool", extra={"tool": tool_name})
    return True, ""


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


def build_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")

    db = DatabaseManager(settings)
    api_key_manager = APIKeyManager(db)
    app.state.api_key_manager = api_key_manager
    pdf = PDFGenerator(settings.pdf_output_dir)

    app_cache = get_cache(
        redis_url=settings.redis_url if settings.redis_enabled else None,
    )
    cache_type = type(app_cache).__name__
    set_app_cache(app_cache)
    logger.info(f"Cache initialized: {cache_type}")

    rag = AdvancedRAG(
        settings.rag_persist_dir,
        settings.rag_collection,
        embedding_model=getattr(settings, "embedding_model", "all-MiniLM-L6-v2"),
        reranker_model="BAAI/bge-reranker-base",
        ingestion_token=settings.rag_ingestion_token,
    )

    memory = MemoryStore(db=db)
    registry = make_registry(
        db=db, pdf=pdf, rag_search_fn=lambda query, k=5: rag.search(query=query, k=k)
    )

    install_metrics(app)
    install_rate_limiter(app, settings)
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

    raw_router = _build_router(settings)
    tracer: LLMTracer | None = None
    if raw_router is not None:
        tracer = LLMTracer(raw_router)
    router = tracer  # traced router used everywhere; None if no providers

    detector = HallucinationDetector(
        high_threshold=settings.hallucination_high_threshold,
        medium_threshold=settings.hallucination_medium_threshold,
    )

    tracker = MLflowTracker(
        tracking_uri=settings.mlflow_tracking_uri,
        experiment_name=settings.mlflow_experiment_name,
        enabled=settings.mlflow_enabled,
    )

    orchestrator = None
    if router is not None:
        orchestrator = ConciergeOrchestrator(
            llm_provider=router,
            rag=rag,
            tool_registry=registry,
            memory_store=memory,
        )

    input_guard = InputGuard()

    # --- AGENT LOGIC ---

    @profile
    async def _agent_reply(session_id: str, user_text: str) -> dict:
        try:
            text = validate_message(user_text)

            # --- Input guardrails ---
            injection_safe, injection_reason = input_guard.check_prompt_injection(text)
            if not injection_safe:
                logger.warning(f"input_guard_blocked: {injection_reason}")
                return {
                    "message": "I'm unable to process that request.",
                    "tool_calls": [],
                    "guardrail": "prompt_injection",
                }

            if not input_guard.check_topic_boundary(text):
                logger.info("input_guard: off-topic request blocked")
                return {
                    "message": (
                        "I am the Grand Chamberlain of the Monster Resort. "
                        "I can only assist with resort and hospitality inquiries."
                    ),
                    "tool_calls": [],
                    "guardrail": "off_topic",
                }

            text, pii_types = input_guard.check_pii(text)

            logger.debug(
                "agent_reply received message",
                extra={"session_id": session_id, "message_length": len(text)},
            )

            if router is None:
                return {"message": "AI services are offline.", "tool_calls": []}

            knowledge = rag.search(text)
            results = knowledge.get("results", [])
            rag_contexts = [r["text"] for r in results]

            # Defense 4: Source attribution — tag each context with its source
            context_lines = []
            for r in results:
                source = r.get("meta", {}).get("source", "unknown")
                context_lines.append(f"[Source: {source}] {r['text']}")
            context_text = "\n".join(context_lines)

            current_date_str = datetime.now().strftime("%Y-%m-%d")

            system_prompt_content = (
                f"You are the 'Grand Chamberlain' of the Monster Resort. Today is {current_date_str}.\n"
                f"ACTIVE SESSION ID: {session_id}\n\n"
                "RESORT KNOWLEDGE BASE (MANDATORY - Use these details FIRST to describe the stay):\n"
                f"{context_text}\n\n"
                "MANDATORY RULES:\n"
                "1. ALWAYS base your answer on the RESORT KNOWLEDGE BASE above when it contains relevant information.\n"
                "2. DO NOT invent details that contradict or are not present in the knowledge base.\n"
                "3. If the knowledge base has information about the topic, quote or paraphrase it directly.\n"
                "4. If no relevant info is found in the knowledge base, "
                "say 'I do not have specific details on that in our records.'\n"
                "5. THE WELCOME: When 'book_room' succeeds, describe the specific "
                "atmosphere of the property from the knowledge base.\n"
                "6. THE STATUS: Use the phrase 'The dark seal has been set upon the ledger.'\n"
                "7. MANDATORY TONE: Sophisticated, gothic, ultra-luxurious. No modern slang.\n"
                "8. FAREWELL: End with 'We await your shadow' or 'May your rest be eternal (until check-out).'\n"
            )

            past_messages = memory.get_messages(session_id)
            chat_history: list[LLMMessage] = [
                LLMMessage(role="system", content=system_prompt_content)
            ]
            for m in past_messages:
                if m["role"] in ["user", "assistant"]:
                    chat_history.append(
                        LLMMessage(role=m["role"], content=m["content"])
                    )
            chat_history.append(LLMMessage(role="user", content=text))

            tool_schemas = registry.get_openai_tool_schemas()

            llm_resp = await router.chat(chat_history, tools=tool_schemas)

            if llm_resp.tool_calls:
                chat_history.append(
                    LLMMessage(
                        role="assistant",
                        content=llm_resp.content,
                        tool_calls=llm_resp.tool_calls,
                    )
                )

                tool_results = []
                for tc in llm_resp.tool_calls:
                    t_name = tc.name
                    t_args = json.loads(tc.arguments)
                    logger.debug(
                        "tool_call_invoked",
                        extra={"tool": t_name, "args": t_args},
                    )

                    # Defense 6: Validate tool call before execution
                    is_valid, error_msg = _validate_tool_call(t_name, t_args)
                    if not is_valid:
                        logger.warning(f"tool_call_blocked: {t_name} — {error_msg}")
                        res = {"ok": False, "error": error_msg, "blocked": True}
                        tool_results.append({"tool": t_name, "result": res})
                        chat_history.append(
                            LLMMessage(
                                role="tool",
                                content=json.dumps(res),
                                tool_call_id=tc.id,
                            )
                        )
                        continue

                    res = await registry.async_execute_with_timing(t_name, **t_args)
                    logger.debug(
                        "tool_call_result",
                        extra={"tool": t_name, "ok": res.get("ok", True)},
                    )

                    tool_results.append({"tool": t_name, "result": res})
                    chat_history.append(
                        LLMMessage(
                            role="tool",
                            content=json.dumps(res),
                            tool_call_id=tc.id,
                        )
                    )

                llm_resp2 = await router.chat(chat_history)
                final_message = llm_resp2.content

                output_guard = OutputGuard(input_pii_types=pii_types)
                out_safe, out_reason = output_guard.check_response(final_message)
                if not out_safe:
                    logger.warning(f"output_guard_blocked: {out_reason}")
                    final_message = (
                        "I must beg your pardon — let me rephrase. "
                        "How else may I assist you with your stay?"
                    )

                confidence = detector.score_response(
                    final_message, rag_contexts, text
                )

                tracker.log_confidence_metrics(confidence, provider=llm_resp2.provider)

                return {
                    "message": final_message,
                    "tool_calls": tool_results,
                    "confidence": confidence.to_dict(),
                    "provider": llm_resp2.provider,
                }

            response_text = llm_resp.content

            output_guard = OutputGuard(input_pii_types=pii_types)
            out_safe, out_reason = output_guard.check_response(response_text)
            if not out_safe:
                logger.warning(f"output_guard_blocked: {out_reason}")
                response_text = (
                    "I must beg your pardon — let me rephrase. "
                    "How else may I assist you with your stay?"
                )

            confidence = detector.score_response(
                response_text, rag_contexts, text
            )
            tracker.log_confidence_metrics(confidence, provider=llm_resp.provider)

            return {
                "message": response_text,
                "tool_calls": [],
                "confidence": confidence.to_dict(),
                "provider": llm_resp.provider,
            }

        except Exception as e:
            import traceback

            logger.error(f"Agent error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"message": f"Error: {str(e)}", "ok": False}

    # --- ROUTES ---

    @app.post("/chat")
    async def chat(payload: dict, _: str = Depends(jwt_or_api_key)):
        session_id = payload.get("session_id") or str(uuid.uuid4())
        user_text = payload.get("message")

        response_data = await _agent_reply(session_id, user_text)

        memory.add_message(session_id, "user", user_text)
        memory.add_message(session_id, "assistant", response_data["message"])

        return {
            "ok": True,
            "reply": response_data["message"],
            "session_id": session_id,
            "tools_used": response_data.get("tool_calls", []),
            "confidence": response_data.get("confidence"),
            "provider": response_data.get("provider"),
        }

    @app.post("/chat/v2")
    async def chat_v2(payload: dict, _: str = Depends(jwt_or_api_key)):
        """Orchestrator-based chat endpoint."""
        session_id = payload.get("session_id") or str(uuid.uuid4())
        user_text = payload.get("message")

        if not user_text:
            raise HTTPException(status_code=400, detail="message is required")

        # --- Input guardrails (v2) ---
        injection_safe, injection_reason = input_guard.check_prompt_injection(user_text)
        if not injection_safe:
            logger.warning(f"input_guard_blocked (v2): {injection_reason}")
            return {
                "ok": True,
                "reply": "I'm unable to process that request.",
                "session_id": session_id,
                "guardrail": "prompt_injection",
            }

        if not input_guard.check_topic_boundary(user_text):
            logger.info("input_guard (v2): off-topic request blocked")
            return {
                "ok": True,
                "reply": (
                    "I am the Grand Chamberlain of the Monster Resort. "
                    "I can only assist with resort and hospitality inquiries."
                ),
                "session_id": session_id,
                "guardrail": "off_topic",
            }

        sanitized_text, pii_types = input_guard.check_pii(user_text)

        if orchestrator is None:
            return {
                "ok": False,
                "reply": "AI services are offline.",
                "session_id": session_id,
            }

        result = await orchestrator.handle(sanitized_text, session_id)

        # --- Output guardrails (v2) ---
        reply = result.response
        output_guard = OutputGuard(input_pii_types=pii_types)
        out_safe, out_reason = output_guard.check_response(reply)
        if not out_safe:
            logger.warning(f"output_guard_blocked (v2): {out_reason}")
            reply = (
                "I must beg your pardon — let me rephrase. "
                "How else may I assist you with your stay?"
            )

        return {
            "ok": True,
            "reply": reply,
            "session_id": session_id,
            "intent": result.plan.intent.value,
            "reasoning": result.plan.reasoning,
            "sources": result.sources,
            "tools_used": [result.tool_result] if result.tool_result else [],
            "confidence": result.confidence.to_dict() if hasattr(result.confidence, "to_dict") else result.confidence,
            "latency_ms": result.latency_ms,
            "token_usage": result.token_usage,
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

    # ── MCP Server ────────────────────────────────────────────────────
    from .core.mcp_server import MCPServer

    mcp = MCPServer(tool_registry=registry) if registry else None

    @app.get("/api/v1/mcp/tools")
    def mcp_list_tools():
        """MCP tool discovery endpoint."""
        if mcp is None:
            return {"tools": []}
        return {"tools": mcp.list_tools()}

    @app.post("/api/v1/mcp/call")
    async def mcp_call_tool(request: dict):
        """MCP tool execution endpoint."""
        if mcp is None:
            return {"content": [{"type": "text", "text": "MCP server not available"}], "isError": True}
        name = request.get("name", "")
        arguments = request.get("arguments", {})
        return await mcp.call_tool(name, arguments)

    @app.get("/api/v1/mcp/info")
    def mcp_server_info():
        """MCP server metadata endpoint."""
        if mcp is None:
            return {"error": "MCP server not available"}
        return mcp.get_server_info()

    knowledge_path = Path.cwd() / "data" / "knowledge"
    if knowledge_path.exists():
        logger.info(f"Ingesting knowledge from {knowledge_path}...")
        rag.ingest_folder(str(knowledge_path), token=settings.rag_ingestion_token)

    return app


app = build_app()
