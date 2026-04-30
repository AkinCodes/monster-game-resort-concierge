from __future__ import annotations
from fastapi.responses import StreamingResponse
import re
import uuid
import os
import secrets
import json
import openai
from datetime import datetime, timezone
from pathlib import Path
from dateutil import parser as date_parser
from fastapi import Depends, FastAPI, HTTPException, Request

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Local module imports
from .cctv.profile_utils import profile

from .config import get_settings

from .back_office.database import DatabaseManager
from .back_office.cache_utils import get_cache, set_app_cache
from .concierge.memory import MemoryStore
from .concierge.guardrails import InputGuard, OutputGuard
from .cctv.monitoring import install_metrics
from .services.pdf_generator import PDFGenerator
from .records_room.advanced_rag import AdvancedRAG
from .security_dept.security import install_rate_limiter, APIKeyManager
from .front_desk.admin_routes import router as admin_router
from .security_dept.auth_mixins import jwt_or_api_key
from .concierge.tools import make_registry, VALID_HOTELS
from .concierge.mcp_server import MCPServer
from .concierge.llm_providers import (
    ModelRouter,
    LLMMessage,
    LLMToolCall,
    LLMResponse,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
)
from .concierge.observability import LLMTracer
from .concierge.orchestrator import ConciergeOrchestrator
from .manager_office.hallucination import HallucinationDetector
from .cctv.mlflow_tracking import MLflowTracker
from .cctv.logging_utils import (
    setup_logging,
    MonsterResortError,
    DatabaseError,
    AIServiceError,
    ValidationError,
)
from .security_dept.auth import create_access_token, verify_token, hash_password, verify_password
from .security_dept.users_db import users_db
from .manager_office.validation import validate_message

# Initialize Logger
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
        # NOTE: If the LLM hallucinates a tool name that doesn't exist (e.g., "delete_user"),
        # this function lets it through with (True, ""). That's OK because the ToolRegistry
        # will reject it at execution time — registry.get(name) returns None and the tool
        # loop returns an error dict. We log a warning here for debugging, but don't block
        # because future tools might be added to the registry without updating this function.
        logger.warning("validate_tool_call_unknown_tool", extra={"tool": tool_name})
    return True, ""


def _build_router(settings) -> ModelRouter | None:
    """Construct LLM providers and router from settings."""
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

    # Initialize cache — Redis if enabled and reachable, otherwise in-memory
    app_cache = get_cache(
        redis_url=settings.redis_url if settings.redis_enabled else None,
    )
    set_app_cache(app_cache)

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
    mcp = MCPServer(tool_registry=registry) if registry else None

    install_metrics(app)
    install_rate_limiter(app, settings)
    app.include_router(admin_router)

    # Build multi-model router
    router = _build_router(settings)
    tracer = LLMTracer(provider=router) if router else None

    # Guardrails
    input_guard = InputGuard()
    output_guard = OutputGuard()

    # Hallucination detector
    detector = HallucinationDetector(
        high_threshold=settings.hallucination_high_threshold,
        medium_threshold=settings.hallucination_medium_threshold,
    )

    # MLflow tracker (graceful noop if disabled)
    tracker = MLflowTracker(
        tracking_uri=settings.mlflow_tracking_uri,
        experiment_name=settings.mlflow_experiment_name,
        enabled=settings.mlflow_enabled,
    )

    # Build orchestrator for v2 endpoint
    orchestrator = None
    if router is not None:
        orchestrator = ConciergeOrchestrator(
            llm_provider=tracer,
            rag=rag,
            tool_registry=registry,
            memory_store=memory,
        )

    # --- AGENT LOGIC ---

    @profile
    async def _agent_reply(session_id: str, user_text: str) -> dict:
        try:
            logger.debug("user_input session=%s message=%s", session_id, user_text)
            text = validate_message(user_text)

            # --- Input guardrails ---
            is_safe, injection_reason = input_guard.check_prompt_injection(user_text)
            if not is_safe:
                logger.warning(f"Prompt injection blocked: {injection_reason}")
                return {
                    "message": "Ah, a most curious incantation — but the Grand Chamberlain is bound by ancient wards. How may I assist you with your resort stay?",
                    "tool_calls": [],
                }

            user_text, pii_found = input_guard.check_pii(user_text)
            if pii_found:
                logger.info(f"PII redacted from input: {pii_found}")

            if not input_guard.check_topic_boundary(user_text):
                return {
                    "message": "A fascinating pursuit, dear guest, but it falls beyond the purview of our resort. Might I help you with a booking, dining, or spa inquiry instead?",
                    "tool_calls": [],
                }

            if router is None:
                return {"message": "AI services are offline.", "tool_calls": []}

            knowledge = rag.search(user_text)
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
                "4. If no relevant info is found in the knowledge base, say 'I do not have specific details on that in our records.'\n"
                "5. THE WELCOME: When 'book_room' succeeds, describe the specific atmosphere of the property from the knowledge base.\n"
                "6. THE STATUS: Use the phrase 'The dark seal has been set upon the ledger.'\n"
                "7. MANDATORY TONE: Sophisticated, gothic, ultra-luxurious. No modern slang.\n"
                "8. FAREWELL: End with 'We await your shadow' or 'May your rest be eternal (until check-out).'\n"
            )

            logger.debug("system_prompt preview=%s", system_prompt_content[:500])

            # Build LLMMessage history
            past_messages = memory.get_messages(session_id)
            chat_history: list[LLMMessage] = [
                LLMMessage(role="system", content=system_prompt_content)
            ]
            for m in past_messages:
                if m["role"] in ["user", "assistant"]:
                    chat_history.append(
                        LLMMessage(role=m["role"], content=m["content"])
                    )
            chat_history.append(LLMMessage(role="user", content=user_text))

            tool_schemas = registry.get_openai_tool_schemas()

            # Phase 1: initial LLM call (may include tool calls)
            llm_resp = await tracer.chat(chat_history, tools=tool_schemas)

            logger.debug("llm_initial_response content=%s", llm_resp.content)

            if llm_resp.tool_calls:
                # Add assistant message with tool calls to history
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
                    logger.debug("tool_call name=%s args=%s", t_name, t_args)

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
                    logger.debug("tool_result name=%s result=%s", t_name, res)

                    tool_results.append({"tool": t_name, "result": res})
                    chat_history.append(
                        LLMMessage(
                            role="tool",
                            content=json.dumps(res),
                            tool_call_id=tc.id,
                        )
                    )

                # Phase 2: synthesis call
                llm_resp2 = await tracer.chat(chat_history)
                final_message = llm_resp2.content

                logger.debug("llm_final_response content=%s", final_message)

                # Confidence scoring
                confidence = detector.score_response(
                    final_message, rag_contexts, user_text
                )

                # Optional MLflow logging
                tracker.log_confidence_metrics(confidence, provider=llm_resp2.provider)

                # --- Output guardrail ---
                output_guard.input_pii_types = pii_found
                resp_safe, resp_reason = output_guard.check_response(final_message)
                if not resp_safe:
                    logger.warning(f"Output guard blocked response: {resp_reason}")
                    final_message = "The Grand Chamberlain must consult the ancient ledgers before responding. Please rephrase your inquiry, dear guest."

                return {
                    "message": final_message,
                    "tool_calls": tool_results,
                    "confidence": confidence.to_dict(),
                    "provider": llm_resp2.provider,
                }

            # No tool calls — direct response
            confidence = detector.score_response(
                llm_resp.content, rag_contexts, user_text
            )
            tracker.log_confidence_metrics(confidence, provider=llm_resp.provider)

            # --- Output guardrail ---
            response_text = llm_resp.content
            output_guard.input_pii_types = pii_found
            resp_safe, resp_reason = output_guard.check_response(response_text)
            if not resp_safe:
                logger.warning(f"Output guard blocked response: {resp_reason}")
                response_text = "The Grand Chamberlain must consult the ancient ledgers before responding. Please rephrase your inquiry, dear guest."

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
        """Orchestrator-based chat endpoint (plan-then-execute)."""
        session_id = payload.get("session_id") or str(uuid.uuid4())
        user_text = payload.get("message")

        if not user_text:
            raise HTTPException(status_code=400, detail="message is required")

        # --- Input guardrails (v2) ---
        is_safe, injection_reason = input_guard.check_prompt_injection(user_text)
        if not is_safe:
            logger.warning(f"v2 prompt injection blocked: {injection_reason}")
            return {
                "ok": True,
                "reply": "Ah, a most curious incantation — but the Grand Chamberlain is bound by ancient wards. How may I assist you with your resort stay?",
                "session_id": session_id,
            }

        user_text, pii_found = input_guard.check_pii(user_text)
        if pii_found:
            logger.info(f"v2 PII redacted from input: {pii_found}")

        if not input_guard.check_topic_boundary(user_text):
            return {
                "ok": True,
                "reply": "A fascinating pursuit, dear guest, but it falls beyond the purview of our resort. Might I help you with a booking, dining, or spa inquiry instead?",
                "session_id": session_id,
            }

        if orchestrator is None:
            return {
                "ok": False,
                "reply": "AI services are offline.",
                "session_id": session_id,
            }

        result = await orchestrator.handle(user_text, session_id)

        # --- Output guardrail (v2) ---
        reply_text = result.response
        output_guard.input_pii_types = pii_found
        resp_safe, resp_reason = output_guard.check_response(reply_text)
        if not resp_safe:
            logger.warning(f"v2 output guard blocked response: {resp_reason}")
            reply_text = "The Grand Chamberlain must consult the ancient ledgers before responding. Please rephrase your inquiry, dear guest."

        return {
            "ok": True,
            "reply": reply_text,
            "session_id": session_id,
            "intent": result.plan.intent.value,
            "reasoning": result.plan.reasoning,
            "sources": result.sources,
            "tools_used": [result.tool_result] if result.tool_result else [],
            "confidence": result.confidence.to_dict() if hasattr(result.confidence, "to_dict") else result.confidence,
            "latency_ms": result.latency_ms,
            "token_usage": result.token_usage,
        }


    # --- TRACES ENDPOINT ---

    @app.get("/api/v1/traces")
    def get_traces():
        if tracer is None:
            return {"traces": [], "summary": {}}
        return {
            "traces": tracer.recent_traces(),
            "summary": tracer.summary(),
        }

    # --- MCP ENDPOINTS ---

    @app.get("/api/v1/mcp/tools")
    def mcp_list_tools():
        if mcp is None:
            return {"tools": []}
        return {"tools": mcp.list_tools()}

    @app.post("/api/v1/mcp/call")
    async def mcp_call_tool(request: dict):
        if mcp is None:
            return {"content": [{"type": "text", "text": "MCP not available"}], "isError": True}
        name = request.get("name", "")
        arguments = request.get("arguments", {})
        return await mcp.call_tool(name, arguments)

    @app.get("/api/v1/mcp/info")
    def mcp_server_info():
        if mcp is None:
            return {"error": "MCP not available"}
        return mcp.get_server_info()

    # Startup Ingestion
    knowledge_path = os.path.join(os.getcwd(), "data", "knowledge")
    if os.path.exists(knowledge_path):
        logger.info(f"Ingesting knowledge from {knowledge_path}...")
        rag.ingest_folder(knowledge_path, token=settings.rag_ingestion_token)

    return app


app = build_app()
