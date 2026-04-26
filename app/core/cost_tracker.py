"""
Cost Tracker — estimates per-request cost from model name and token counts.

Pricing is loaded from configs/model_pricing.yaml at startup.
Update the YAML file when providers change rates — no code changes needed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Tuple

import yaml

logger = logging.getLogger(__name__)

PRICING_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "configs", "model_pricing.yaml"
)


@lru_cache(maxsize=1)
def _load_pricing() -> Dict[str, Tuple[float, float]]:
    """Load model pricing from YAML config. Cached after first call."""
    try:
        with open(PRICING_PATH, "r") as f:
            raw = yaml.safe_load(f) or {}
        pricing = {}
        for model, rates in raw.items():
            if isinstance(rates, dict):
                pricing[model] = (
                    float(rates.get("input", 0.0)),
                    float(rates.get("output", 0.0)),
                )
        logger.info("pricing_loaded", extra={"models": len(pricing)})
        return pricing
    except FileNotFoundError:
        logger.warning("pricing_file_not_found", extra={"path": PRICING_PATH})
        return _fallback_pricing()
    except Exception as exc:
        logger.error("pricing_load_failed", extra={"error": str(exc)})
        return _fallback_pricing()


def _fallback_pricing() -> Dict[str, Tuple[float, float]]:
    """Hardcoded fallback if YAML is missing or corrupt."""
    return {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (2.50, 10.00),
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
    model_pricing = _load_pricing()
    pricing = model_pricing.get(model)

    if pricing is None:
        # Try prefix matching (e.g. "gpt-4o-2024-11-20" -> "gpt-4o")
        for key in model_pricing:
            if model.startswith(key):
                pricing = model_pricing[key]
                break

    if pricing is None:
        logger.warning("cost_tracker_unknown_model", extra={"model": model})
        pricing = model_pricing.get("gpt-4o-mini", (0.15, 0.60))

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
