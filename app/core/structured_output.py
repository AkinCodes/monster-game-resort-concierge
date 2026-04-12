"""
Structured Output Validation
=============================

Validates LLM JSON responses against Pydantic schemas with retry logic.
Provides domain-specific models for the Monster Resort Concierge and a
reusable parser that extracts JSON from raw LLM text.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class StructuredOutputError(Exception):
    """Raised when structured output parsing fails after all retries."""

    def __init__(self, message: str, raw_response: str, errors: list[str]):
        super().__init__(message)
        self.raw_response = raw_response
        self.errors = errors


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class BookingIntent(BaseModel):
    """Parsed intent for a booking-related request."""

    action: str  # "book", "search", "cancel"
    guest_name: Optional[str] = None
    room_type: Optional[str] = None
    dates: Optional[str] = None


class SearchQuery(BaseModel):
    """Parsed intent for a knowledge-base search."""

    query: str
    category: str  # "amenities", "rooms", "policies"
    top_k: int = 5


class ConciergeResponse(BaseModel):
    """Structured response envelope returned by the concierge."""

    answer: str
    confidence: str  # "high", "medium", "low"
    sources: list[str] = []
    suggested_tools: list[str] = []


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class StructuredOutputParser:
    """Validates LLM JSON output against Pydantic schemas with retry logic."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    # -- public API ---------------------------------------------------------

    async def parse(
        self,
        llm_response: str,
        schema: Type[T],
        retry_fn=None,
    ) -> T:
        """Parse LLM output into a Pydantic model.

        Args:
            llm_response: Raw LLM text (should contain JSON).
            schema: Pydantic model class to validate against.
            retry_fn: Optional async callable ``(error_msg: str) -> str`` that
                      re-prompts the LLM with the validation error so it can
                      produce a corrected response.

        Returns:
            Validated Pydantic model instance.

        Raises:
            StructuredOutputError: If parsing fails after all retries.
        """
        accumulated_errors: list[str] = []
        current_text = llm_response

        for attempt in range(1 + self.max_retries):
            try:
                json_str = self._extract_json(current_text)
                data = json.loads(json_str)
                result = schema.model_validate(data)
                if attempt > 0:
                    self.logger.info(
                        "Structured output parsed on retry %d for %s",
                        attempt,
                        schema.__name__,
                    )
                return result

            except json.JSONDecodeError as exc:
                error_msg = f"JSON decode error: {exc}"
                accumulated_errors.append(error_msg)
                self.logger.warning(
                    "Attempt %d/%d — %s", attempt + 1, 1 + self.max_retries, error_msg
                )

            except ValidationError as exc:
                error_msg = f"Validation error: {exc}"
                accumulated_errors.append(error_msg)
                self.logger.warning(
                    "Attempt %d/%d — %s", attempt + 1, 1 + self.max_retries, error_msg
                )

            # Retry with the LLM if a retry function was provided
            if retry_fn is not None and attempt < self.max_retries:
                feedback = (
                    f"Your previous response could not be parsed. "
                    f"Error: {accumulated_errors[-1]}\n\n"
                    f"Please respond with ONLY valid JSON matching this schema:\n"  # noqa: E231
                    f"{json.dumps(schema.model_json_schema(), indent=2)}"
                )
                try:
                    current_text = await retry_fn(feedback)
                except Exception as retry_exc:
                    accumulated_errors.append(f"Retry call failed: {retry_exc}")
                    break
            elif attempt < self.max_retries:
                # No retry function — nothing more we can do
                break

        raise StructuredOutputError(
            message=(
                f"Failed to parse LLM response into {schema.__name__} "
                f"after {len(accumulated_errors)} attempt(s)"
            ),
            raw_response=llm_response,
            errors=accumulated_errors,
        )

    def get_schema_prompt(self, schema: Type[T]) -> str:
        """Generate a prompt instruction telling the LLM the expected JSON format.

        The prompt includes the full JSON-Schema so the model knows exactly
        which fields are required, their types, and any constraints.
        """
        json_schema = schema.model_json_schema()
        schema_str = json.dumps(json_schema, indent=2)
        return (
            "Respond with ONLY a valid JSON object (no markdown fences, no "
            "commentary) that conforms to this schema:\n\n"
            f"```json\n{schema_str}\n```"  # noqa: W604
        )

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> str:
        """Best-effort extraction of JSON from LLM text.

        Handles:
          1. Bare JSON objects
          2. JSON inside markdown code fences (```json ... ``` or ``` ... ```)
          3. JSON embedded in surrounding prose
        """
        # Strip markdown fences first
        fence_match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", text, re.DOTALL
        )
        if fence_match:
            return fence_match.group(1).strip()

        # Try to find a top-level JSON object
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            return brace_match.group(0).strip()

        # Fall back to the full text
        return text.strip()
