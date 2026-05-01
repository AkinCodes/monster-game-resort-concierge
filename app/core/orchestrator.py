"""Multi-Agent Orchestrator: Planner classifies intent, Executor acts on it."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional

from .cost_tracker import CostAccumulator
from .llm_providers import LLMMessage, LLMProvider, LLMResponse
from .memory import MemoryStore
from .prompt_loader import load_prompt
from .structured_output import StructuredOutputParser
from .tools import ToolRegistry, VALID_HOTELS

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    KNOWLEDGE = "knowledge"
    TOOL = "tool"
    CLARIFY = "clarify"
    CHITCHAT = "chitchat"


@dataclass
class Plan:
    """The planner's decision."""

    intent: IntentType
    tool_name: Optional[str] = None
    tool_args: dict = field(default_factory=dict)
    search_query: Optional[str] = None
    reasoning: str = ""


@dataclass
class ExecutionResult:
    """The executor's output."""

    response: str
    plan: Plan
    tool_result: Optional[dict] = None
    sources: list[str] = field(default_factory=list)
    rag_contexts: List[str] = field(default_factory=list)
    latency_ms: float = 0
    token_usage: dict = field(default_factory=dict)
    confidence: object = None
    claim_verification: Optional[object] = None


class ConciergeOrchestrator:
    """Two-agent orchestrator: Planner decides, Executor acts."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        rag: Any,  # VectorRAG or AdvancedRAG instance
        tool_registry: ToolRegistry,
        memory_store: MemoryStore,
        detector=None,
    ):
        self.llm = llm_provider
        self.rag = rag
        self.tools = tool_registry
        self.memory = memory_store
        self.detector = detector
        self._total_planner_tokens = 0
        self._total_executor_tokens = 0
        self._costs = CostAccumulator()

    async def plan(self, user_message: str, session_id: str) -> Plan:
        """Classify user intent and create an execution plan; falls back to chitchat on error."""
        start = time.monotonic()

        available_tools = self.tools.list()
        tool_descriptions = [f"{t.name}: {t.description}" for t in available_tools]
        tool_list = "; ".join(tool_descriptions) if tool_descriptions else "(none)"

        history = self.memory.get_messages(session_id, limit=5)
        history_text = self._format_history(history)

        system_prompt = load_prompt("planner", tool_list=tool_list)

        user_content = user_message
        if history_text:
            user_content = (
                f"Recent conversation:\n{history_text}\n\nCurrent message: {user_message}"  # noqa: E231
            )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_content),
        ]

        try:
            response_format = None
            if getattr(self.llm, "supports_response_format", False):
                response_format = {"type": "json_object"}

            response: LLMResponse = await self.llm.chat(
                messages, response_format=response_format
            )
            self._track_tokens("planner", response.usage, response)

            plan = self._parse_plan(response.content)

            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info(
                "planner_completed",
                extra={
                    "intent": plan.intent.value,
                    "tool_name": plan.tool_name,
                    "reasoning": plan.reasoning,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "tokens": response.usage,
                },
            )
            return plan

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(
                "planner_failed_falling_back_to_chitchat",
                extra={"error": str(exc), "elapsed_ms": round(elapsed_ms, 2)},
            )
            return Plan(
                intent=IntentType.CHITCHAT,
                reasoning=f"Planner failed ({exc}), falling back to chitchat",
            )

    def _parse_plan(self, raw: str) -> Plan:
        """Parse planner JSON into a Plan; falls back to keyword heuristic."""
        data = None

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

        if data is None:
            try:
                extracted = StructuredOutputParser._extract_json(raw)
                data = json.loads(extracted)
            except json.JSONDecodeError:
                data = None

        if data is None:
            logger.warning(
                "planner_json_parse_failed",
                extra={"raw": raw[:200]},
            )
            # Heuristic fallback
            lower = raw.lower()
            if any(kw in lower for kw in ["book", "reserve", "lookup", "get_booking"]):
                return Plan(
                    intent=IntentType.TOOL,
                    reasoning="JSON parse failed; detected tool keywords",
                )
            if any(kw in lower for kw in ["amenities", "pool", "spa", "restaurant"]):
                return Plan(
                    intent=IntentType.KNOWLEDGE,
                    search_query=raw[:100],
                    reasoning="JSON parse failed; detected knowledge keywords",
                )
            return Plan(
                intent=IntentType.CHITCHAT,
                reasoning="JSON parse failed; defaulting to chitchat",
            )

        intent_str = data.get("intent", "chitchat").lower()
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.CHITCHAT

        return Plan(
            intent=intent,
            tool_name=data.get("tool_name"),
            tool_args=data.get("tool_args") or {},
            search_query=data.get("search_query"),
            reasoning=data.get("reasoning", ""),
        )

    async def execute(
        self, plan: Plan, user_message: str, session_id: str
    ) -> ExecutionResult:
        """Agent 2: Execute the plan created by the planner."""
        start = time.monotonic()

        try:
            if plan.intent == IntentType.KNOWLEDGE:
                result = await self._execute_knowledge(plan, user_message, session_id)
            elif plan.intent == IntentType.TOOL:
                result = await self._execute_tool(plan, user_message, session_id)
            elif plan.intent == IntentType.CLARIFY:
                result = await self._execute_clarify(plan, user_message, session_id)
            else:
                result = await self._execute_chitchat(plan, user_message, session_id)
        except Exception as exc:
            logger.exception(
                "executor_failed",
                extra={"intent": plan.intent.value, "error": str(exc)},
            )
            result = ExecutionResult(
                response=(
                    "I'm terribly sorry, something went wrong on my end. "
                    "Could you try rephrasing your request?"
                ),
                plan=plan,
            )

        result.latency_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "executor_completed",
            extra={
                "intent": plan.intent.value,
                "latency_ms": result.latency_ms,
                "sources_count": len(result.sources),
                "tokens": result.token_usage,
            },
        )
        return result

    async def _execute_knowledge(
        self, plan: Plan, user_message: str, session_id: str
    ) -> ExecutionResult:
        """Search RAG, build context, generate response."""
        query = plan.search_query or user_message
        rag_results = self.rag.search(query, k=5)

        docs = rag_results.get("results", [])
        context_parts = []
        sources = []
        for doc in docs:
            text = doc.get("text", "")
            source = doc.get("meta", {}).get("source", "unknown")
            if text:
                context_parts.append(text)
                sources.append(source)

        context = "\n---\n".join(context_parts) if context_parts else "(no results found)"
        history = self.memory.get_messages(session_id, limit=5)

        prompt = load_prompt(
            "executor.knowledge",
            context=context,
            history=self._format_history(history),
            question=user_message,
        )

        response = await self.llm.chat(
            [
                LLMMessage(role="system", content=prompt),
                LLMMessage(role="user", content=user_message),
            ]
        )
        self._track_tokens("executor", response.usage, response)

        return ExecutionResult(
            response=response.content,
            plan=plan,
            sources=sources,
            rag_contexts=context_parts,
            token_usage=response.usage,
        )

    async def _execute_tool(
        self, plan: Plan, user_message: str, session_id: str
    ) -> ExecutionResult:
        """Execute a registered tool and format the result."""
        if not plan.tool_name:
            return ExecutionResult(
                response=(
                    "I understood you want to perform an action, but I could"
                    " not determine which one. Could you be more specific?"
                ),
                plan=plan,
            )

        tool = self.tools.get(plan.tool_name)
        if not tool:
            available = [t.name for t in self.tools.list()]
            return ExecutionResult(
                response=f"I don't have a tool called '{plan.tool_name}'. Available tools: {', '.join(available)}.",
                plan=plan,
            )

        valid, reason = self._validate_tool_call(
            plan.tool_name, plan.tool_args
        )
        if not valid:
            return ExecutionResult(response=reason, plan=plan)

        args = dict(plan.tool_args)
        if "session_id" not in args:
            args["session_id"] = session_id

        request_id = str(uuid.uuid4())
        tool_result = await self.tools.async_execute_with_timing(
            plan.tool_name, request_id=request_id, **args
        )

        prompt = load_prompt(
            "executor.tool_result",
            tool_name=plan.tool_name,
            tool_result=json.dumps(tool_result, default=str),
            question=user_message,
        )

        response = await self.llm.chat(
            [
                LLMMessage(role="system", content=prompt),
                LLMMessage(role="user", content=user_message),
            ]
        )
        self._track_tokens("executor", response.usage, response)

        return ExecutionResult(
            response=response.content,
            plan=plan,
            tool_result=tool_result if isinstance(tool_result, dict) else {"result": tool_result},
            token_usage=response.usage,
        )

    async def _execute_clarify(
        self, plan: Plan, user_message: str, session_id: str
    ) -> ExecutionResult:
        """Generate a clarification question."""
        history = self.memory.get_messages(session_id, limit=5)

        prompt = load_prompt(
            "executor.clarify",
            reasoning=plan.reasoning,
            history=self._format_history(history),
            question=user_message,
        )

        response = await self.llm.chat(
            [
                LLMMessage(role="system", content=prompt),
                LLMMessage(role="user", content=user_message),
            ]
        )
        self._track_tokens("executor", response.usage, response)

        return ExecutionResult(
            response=response.content,
            plan=plan,
            token_usage=response.usage,
        )

    async def _execute_chitchat(
        self, plan: Plan, user_message: str, session_id: str
    ) -> ExecutionResult:
        """Generate a direct conversational response."""
        history = self.memory.get_messages(session_id, limit=5)

        prompt = load_prompt(
            "executor.chitchat",
            history=self._format_history(history),
            question=user_message,
        )

        response = await self.llm.chat(
            [
                LLMMessage(role="system", content=prompt),
                LLMMessage(role="user", content=user_message),
            ]
        )
        self._track_tokens("executor", response.usage, response)

        return ExecutionResult(
            response=response.content,
            plan=plan,
            token_usage=response.usage,
        )

    async def handle(self, user_message: str, session_id: str) -> ExecutionResult:
        """Main entry point: plan, execute, save to memory."""
        overall_start = time.monotonic()

        plan = await self.plan(user_message, session_id)
        logger.info(
            "orchestrator_plan_decided",
            extra={
                "intent": plan.intent.value,
                "reasoning": plan.reasoning,
                "session_id": session_id,
            },
        )

        result = await self.execute(plan, user_message, session_id)

        if plan.intent == IntentType.KNOWLEDGE and self.detector:
            try:
                from ..validation.hallucination import ConfidenceLevel

                result.confidence = self.detector.score_response(
                    result.response, result.rag_contexts
                )
                if result.confidence.level != ConfidenceLevel.HIGH:
                    result.claim_verification = (
                        self.detector.verify_claims(
                            result.response, result.rag_contexts
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "hallucination_detection_failed",
                    extra={"error": str(exc)},
                )

        self.memory.add_message(session_id, "user", user_message)
        self.memory.add_message(session_id, "assistant", result.response)

        total_ms = round((time.monotonic() - overall_start) * 1000, 2)
        logger.info(
            "orchestrator_handle_completed",
            extra={
                "session_id": session_id,
                "intent": plan.intent.value,
                "total_ms": total_ms,
                "planner_tokens_total": self._total_planner_tokens,
                "executor_tokens_total": self._total_executor_tokens,
                "estimated_cost_usd": self._costs.total_cost_usd,
            },
        )

        return result

    @staticmethod
    def _validate_tool_call(
        tool_name: str, tool_args: dict
    ) -> tuple[bool, str]:
        """Validate tool call arguments before execution."""
        if tool_name == "book_room":
            hotel = tool_args.get("hotel_name", "")
            if hotel not in VALID_HOTELS:
                return (
                    False,
                    f"Blocked: unknown hotel '{hotel}'."
                    " Not in official registry.",
                )
        elif tool_name == "get_booking":
            booking_id = tool_args.get("booking_id", "")
            if not booking_id or not booking_id.strip():
                return False, "Blocked: booking_id cannot be empty."
        elif tool_name == "search_amenities":
            query = tool_args.get("query", "")
            if not query or not query.strip():
                return False, "Blocked: search query cannot be empty."
            if len(query) > 500:
                return (
                    False,
                    "Blocked: search query exceeds 500 character limit.",
                )
        else:
            logger.warning(
                "validate_tool_call_unknown_tool",
                extra={"tool": tool_name},
            )
        return True, ""

    def _format_history(self, messages: list[dict]) -> str:
        """Format conversation history for prompt injection."""
        if not messages:
            return "(no prior conversation)"
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _track_tokens(self, agent: str, usage: dict, response: LLMResponse | None = None) -> None:
        """Accumulate token counts and estimated cost."""
        total = usage.get("total_tokens", 0)
        if agent == "planner":
            self._total_planner_tokens += total
        else:
            self._total_executor_tokens += total

        model = response.model if response else ""
        if model:
            cost = self._costs.record(model, usage)
            logger.debug(
                "cost_tracked",
                extra={"agent": agent, "model": model, "cost_usd": cost},
            )

    def get_token_stats(self) -> dict:
        """Return cumulative token usage and estimated cost."""
        return {
            "planner_tokens": self._total_planner_tokens,
            "executor_tokens": self._total_executor_tokens,
            "total_tokens": self._total_planner_tokens + self._total_executor_tokens,
            "estimated_cost": self._costs.summary(),
        }
