"""
Cost Tracker — estimates per-request cost from model name and token counts.

Pricing is approximate and based on published rates as of early 2025.
Add or update entries in ``MODEL_PRICING`` as models change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Prices per 1M tokens (input, output) in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Anthropic
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    # Ollama / local — free
    "llama3": (0.0, 0.0),
}


def estimate_cost(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> float:
    """Return estimated cost in USD for a single LLM call.

    Falls back to gpt-4o-mini pricing if the model is unknown so the
    tracker never crashes — it just logs a warning.
    """
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        # Try prefix matching (e.g. "gpt-4o-2024-11-20" -> "gpt-4o")
        for key in MODEL_PRICING:
            if model.startswith(key):
                pricing = MODEL_PRICING[key]
                break

    if pricing is None:
        logger.warning("cost_tracker_unknown_model", extra={"model": model})
        pricing = MODEL_PRICING["gpt-4o-mini"]

    input_cost = (prompt_tokens / 1_000_000) * pricing[0]
    output_cost = (completion_tokens / 1_000_000) * pricing[1]
    return round(input_cost + output_cost, 6)


@dataclass
class CostAccumulator:
    """Tracks cumulative cost across multiple LLM calls."""

    total_cost_usd: float = 0.0
    call_count: int = 0
    _by_model: dict[str, float] = field(default_factory=dict)

    def record(self, model: str, usage: dict) -> float:
        """Record a single call's cost. Returns the cost of this call."""
        cost = estimate_cost(
            model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        self.total_cost_usd = round(self.total_cost_usd + cost, 6)
        self.call_count += 1
        self._by_model[model] = round(self._by_model.get(model, 0.0) + cost, 6)
        return cost

    def summary(self) -> dict:
        return {
            "total_cost_usd": self.total_cost_usd,
            "call_count": self.call_count,
            "by_model": dict(self._by_model),
        }
