"""
Multi-Agent Orchestrator for Monster Resort Concierge.

Separates PLANNING (what to do) from EXECUTION (how to do it).
This is a production pattern used at scale -- the planner is cheap and fast,
the executor handles the expensive work.

Architecture:
    User query --> Planner (lightweight LLM) --> Plan --> Executor --> Response

The planner classifies intent into one of four categories:
    - knowledge: search the RAG for resort information
    - tool: invoke a registered tool (book_room, get_booking, etc.)
    - clarify: ask the user for missing information
    - chitchat: respond directly without tools
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .llm_providers import LLMMessage, LLMProvider, LLMResponse
from .memory import MemoryStore
from .structured_output import StructuredOutputParser
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


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
    latency_ms: float = 0
    token_usage: dict = field(default_factory=dict)
    confidence: object = None


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
You are the Monster Resort Concierge planner. Your job is to classify the \
user's intent and decide what action to take. You must respond with ONLY a \
JSON object, no other text.

Available tools: {tool_list}

Intent categories:
- "knowledge" -- the user is asking about resort information, amenities, \
policies, or anything that can be answered from the knowledge base.
- "tool" -- the user wants to perform an action (book a room, look up a \
booking, etc.). You must specify tool_name and tool_args.
- "clarify" -- the user's request is ambiguous or missing required \
information. Specify what you need in the reasoning field.
- "chitchat" -- greeting, small talk, or anything that does not need tools \
or knowledge search.

Respond with this exact JSON structure:
{{"intent": "<knowledge|tool|clarify|chitchat>", "tool_name": null, \
"tool_args": {{}}, "search_query": null, "reasoning": "<brief explanation>"}}\
"""

EXECUTOR_KNOWLEDGE_PROMPT = """\
You are the Monster Resort Concierge. Answer the guest's question using \
ONLY the context provided below. If the context does not contain the answer, \
say so honestly -- do not invent information.

Context from resort knowledge base:
{context}

Conversation history:
{history}

Guest's question: {question}\
"""

EXECUTOR_CLARIFY_PROMPT = """\
You are the Monster Resort Concierge. The guest's request needs \
clarification. Ask a friendly, specific follow-up question.

What needs clarification: {reasoning}

Conversation history:
{history}

Guest's message: {question}\
"""

EXECUTOR_CHITCHAT_PROMPT = """\
You are the Monster Resort Concierge at a luxury monster-themed resort. \
Respond warmly and in character. Keep it brief and helpful.

Conversation history:
{history}

Guest: {question}\
"""

EXECUTOR_TOOL_RESULT_PROMPT = """\
You are the Monster Resort Concierge. Summarize the following tool result \
for the guest in a friendly, helpful way.

Tool: {tool_name}
Result: {tool_result}

Guest's original request: {question}\
"""


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class ConciergeOrchestrator:
    """Two-agent orchestrator: Planner decides, Executor acts."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        rag: Any,  # VectorRAG or AdvancedRAG instance
        tool_registry: ToolRegistry,
        memory_store: MemoryStore,
    ):
        self.llm = llm_provider
        self.rag = rag
        self.tools = tool_registry
        self.memory = memory_store
        self._total_planner_tokens = 0
        self._total_executor_tokens = 0

    # -- Agent 1: Planner --------------------------------------------------

    async def plan(self, user_message: str, session_id: str) -> Plan:
        """Agent 1: Analyze the user's intent and create an execution plan.

        Uses a lightweight LLM call with a structured prompt to classify
        the intent and extract parameters. Falls back to chitchat on error.
        """
        start = time.monotonic()

        # Build tool list for the planner prompt
        available_tools = self.tools.list()
        tool_descriptions = [f"{t.name}: {t.description}" for t in available_tools]
        tool_list = "; ".join(tool_descriptions) if tool_descriptions else "(none)"

        # Get recent conversation for context
        history = self.memory.get_messages(session_id, limit=5)
        history_text = self._format_history(history)

        system_prompt = PLANNER_SYSTEM_PROMPT.format(tool_list=tool_list)

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
            response: LLMResponse = await self.llm.chat(messages)
            self._track_tokens("planner", response.usage)

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
        """Parse the planner's JSON response into a Plan object.

        Uses StructuredOutputParser._extract_json() for robust JSON extraction
        that handles markdown fences, surrounding prose, and other LLM quirks.
        """
        try:
            extracted = StructuredOutputParser._extract_json(raw)
            data = json.loads(extracted)
        except json.JSONDecodeError as exc:
            logger.warning(
                "planner_json_parse_failed",
                extra={"raw": raw[:200], "error": str(exc)},
            )
            # Heuristic fallback: check for keywords in raw text
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

    # -- Agent 2: Executor --------------------------------------------------

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

        # Extract documents and sources from RAG results
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

        prompt = EXECUTOR_KNOWLEDGE_PROMPT.format(
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
        self._track_tokens("executor", response.usage)

        return ExecutionResult(
            response=response.content,
            plan=plan,
            sources=sources,
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

        # Inject session_id if the tool expects it
        args = dict(plan.tool_args)
        if "session_id" not in args:
            args["session_id"] = session_id

        request_id = str(uuid.uuid4())
        tool_result = await self.tools.async_execute_with_timing(
            plan.tool_name, request_id=request_id, **args
        )

        # Generate a human-friendly summary of the tool result
        prompt = EXECUTOR_TOOL_RESULT_PROMPT.format(
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
        self._track_tokens("executor", response.usage)

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

        prompt = EXECUTOR_CLARIFY_PROMPT.format(
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
        self._track_tokens("executor", response.usage)

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

        prompt = EXECUTOR_CHITCHAT_PROMPT.format(
            history=self._format_history(history),
            question=user_message,
        )

        response = await self.llm.chat(
            [
                LLMMessage(role="system", content=prompt),
                LLMMessage(role="user", content=user_message),
            ]
        )
        self._track_tokens("executor", response.usage)

        return ExecutionResult(
            response=response.content,
            plan=plan,
            token_usage=response.usage,
        )

    # -- Top-level entry point -----------------------------------------------

    async def handle(self, user_message: str, session_id: str) -> ExecutionResult:
        """Full orchestration: plan then execute.

        This is the main entry point. It runs the planner, logs the decision,
        runs the executor, and saves the exchange to memory.
        """
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

        # Hallucination detection for knowledge responses
        if plan.intent == IntentType.KNOWLEDGE:
            try:
                from ..manager_office.hallucination import HallucinationDetector

                hal_detector = HallucinationDetector()
                result.confidence = hal_detector.score_response(
                    result.response, result.sources, user_message
                )
            except Exception as exc:
                logger.warning(
                    "hallucination_detection_failed",
                    extra={"error": str(exc)},
                )

        # Save exchange to memory
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
            },
        )

        return result

    # -- Helpers -------------------------------------------------------------

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

    def _track_tokens(self, agent: str, usage: dict) -> None:
        """Accumulate token counts for cost tracking."""
        total = usage.get("total_tokens", 0)
        if agent == "planner":
            self._total_planner_tokens += total
        else:
            self._total_executor_tokens += total

    def get_token_stats(self) -> dict:
        """Return cumulative token usage split by agent."""
        return {
            "planner_tokens": self._total_planner_tokens,
            "executor_tokens": self._total_executor_tokens,
            "total_tokens": self._total_planner_tokens + self._total_executor_tokens,
        }


# ---------------------------------------------------------------------------
# Demo / __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import asyncio
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    async def demo():
        """Run the orchestrator with a few example queries.

        Requires:
            - OPENAI_API_KEY set in environment (or adapt for another provider)
            - A populated RAG store and database (or use mocks below)
        """
        # -- Try real providers first, fall back to mocks --------------------
        api_key = os.getenv("OPENAI_API_KEY")

        if api_key:
            from .llm_providers import OpenAIProvider

            llm = OpenAIProvider(api_key=api_key, model="gpt-4o-mini")
            print("Using OpenAI provider (gpt-4o-mini)")
        else:
            print("No OPENAI_API_KEY found. Using mock LLM for demo.\n")
            llm = _MockLLMProvider()

        rag = _MockRAG()
        tool_registry = _MockToolRegistry()
        memory = _MockMemoryStore()

        orchestrator = ConciergeOrchestrator(
            llm_provider=llm,
            rag=rag,
            tool_registry=tool_registry,
            memory_store=memory,
        )

        # -- Example queries -------------------------------------------------
        examples = [
            ("Hello! I just arrived at the resort.", "greeting"),
            ("What amenities does the Vampire Manor have?", "knowledge"),
            ("I'd like to book a room.", "clarify (missing details)"),
            ("Book a deluxe room at Vampire Manor for Count Dracula, Jan 1-3", "tool"),
        ]

        session_id = "demo-session-001"

        for query, expected_type in examples:
            print(f"\n{'='*60}")
            print(f"Guest: {query}")
            print(f"Expected intent: {expected_type}")
            print("-" * 60)

            result = await orchestrator.handle(query, session_id)

            print(f"Intent:  {result.plan.intent.value}")
            print(f"Reason:  {result.plan.reasoning}")
            print(f"Latency: {result.latency_ms:.1f}ms")  # noqa: E231
            if result.sources:
                print(f"Sources: {result.sources}")
            if result.tool_result:
                print(f"Tool:    {result.tool_result}")
            print(f"\nConcierge: {result.response}")

        # -- Token stats -----------------------------------------------------
        stats = orchestrator.get_token_stats()
        print(f"\n{'='*60}")
        print(f"Token usage -- planner: {stats['planner_tokens']}, "
              f"executor: {stats['executor_tokens']}, "
              f"total: {stats['total_tokens']}")

    # -- Mock classes for demo without real services --------------------------

    class _MockLLMProvider:
        """Fake LLM that returns canned JSON for planner, prose for executor."""

        name = "mock"

        async def chat(self, messages, tools=None, model=None):
            content = messages[-1].content if messages else ""
            system = messages[0].content if messages else ""

            # If this is a planner call (system prompt has JSON schema instructions)
            if "intent" in system and "tool_name" in system:
                plan = self._classify(content)
                return LLMResponse(
                    content=json.dumps(plan),
                    model="mock",
                    provider="mock",
                    usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
                )

            # Otherwise it is an executor call
            return LLMResponse(
                content=f"[Mock response] I'd be happy to help with: {content[:80]}",
                model="mock",
                provider="mock",
                usage={"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            )

        @staticmethod
        def _classify(text: str) -> dict:
            lower = text.lower()
            if any(w in lower for w in ["hello", "hi", "arrived", "hey"]):
                return {"intent": "chitchat", "reasoning": "Greeting detected"}
            if any(w in lower for w in ["amenities", "pool", "spa", "restaurant", "what"]):
                return {"intent": "knowledge", "search_query": text[:100],
                        "reasoning": "Information question"}
            if any(w in lower for w in ["book a room", "reserve"]) and "deluxe" not in lower:
                return {"intent": "clarify",
                        "reasoning": "Missing guest name, dates, or hotel"}
            if "book" in lower:
                return {"intent": "tool", "tool_name": "book_room",
                        "tool_args": {"guest_name": "Count Dracula",
                                      "hotel_name": "Vampire Manor: Eternal Night Inn",
                                      "room_type": "deluxe",
                                      "check_in": "2026-01-01",
                                      "check_out": "2026-01-03"},
                        "reasoning": "Booking request with details"}
            return {"intent": "chitchat", "reasoning": "General conversation"}

        def translate_tool_schemas(self, schemas):
            return schemas

    class _MockRAG:
        """Fake RAG that returns canned search results."""

        def search(self, query: str, k: int = 5) -> dict:
            return {
                "results": [
                    {
                        "text": (
                            "Vampire Manor features a blood-red infinity pool, "
                            "24-hour coffin spa, moonlit dining terrace, and "
                            "complimentary bat-wing shuttle service."
                        ),
                        "meta": {"source": "vampire_manor_brochure.md"},
                        "score": 0.12,
                    }
                ]
            }

    class _MockToolRegistry:
        """Fake ToolRegistry for demo purposes."""

        def list(self):
            from .tools import Tool

            return [
                Tool(name="book_room", description="Create a new booking", fn=lambda: None),
                Tool(name="get_booking", description="Look up a booking", fn=lambda: None),
                Tool(name="search_amenities", description="Search resort knowledge", fn=lambda: None),
            ]

        def get(self, name: str):
            tools = {t.name: t for t in self.list()}
            return tools.get(name)

        async def async_execute_with_timing(self, name: str, **kwargs):
            return {
                "ok": True,
                "booking_id": "MOCK-001",
                "message": f"Mock booking at {kwargs.get('hotel_name', 'unknown')}",
            }

    class _MockMemoryStore:
        """In-memory conversation store for demo."""

        def __init__(self):
            self._messages: dict[str, list] = {}

        def get_messages(self, session_id: str, limit: int = 50) -> list[dict]:
            return self._messages.get(session_id, [])[-limit:]

        def add_message(self, session_id: str, role: str, content: str) -> None:
            self._messages.setdefault(session_id, []).append(
                {"role": role, "content": content}
            )

    asyncio.run(demo())
