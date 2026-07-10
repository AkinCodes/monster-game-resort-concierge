"""DeepEval CI regression gate over the 20-case golden set.

This module wraps the existing golden evaluation set
(``data/eval_cases.json``) as DeepEval ``LLMTestCase`` objects and asserts
metric thresholds so that a *quality* regression fails the build the same
way a broken unit test does.

Design goals (why it looks the way it does):

* **CI must be robust without secrets.**  The default suite runs entirely
  offline.  It uses the repo's OWN three-tier hallucination detector
  (``app.validation.hallucination.HallucinationDetector``) wrapped as a
  custom DeepEval ``BaseMetric`` -- no external LLM judge, no API key.
* **Live LLM-judge metrics are opt-in.**  DeepEval's built-in metrics
  (``AnswerRelevancyMetric``, ``FaithfulnessMetric``, ``GEval``) call an
  LLM judge and therefore need ``OPENAI_API_KEY``.  Those tests are gated
  behind the ``RUN_LIVE_EVALS`` env flag and skipped otherwise, so CI is
  green without a key while the live path is a single flag away locally.

Thresholds were calibrated from a real baseline run of the current
``main`` pipeline (the deterministic ``MockPipelineRunner`` used by
``scripts/eval_harness.py``).  Floors are set *below* the observed
baseline so ordinary scoring noise does not false-trip the gate.  See
``EVALUATION.md`` -> "CI eval gate" for the numbers and the rationale.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
from pathlib import Path
from typing import Dict, List

import pytest

from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from app.validation.hallucination import HallucinationDetector
from scripts.eval_harness import MockPipelineRunner

# ---------------------------------------------------------------------------
# Configuration / calibrated thresholds
# ---------------------------------------------------------------------------
# Baseline (mock pipeline on current main, 20 golden cases):
#   grounding/hallucination:  mean 0.682, min 0.620, max 0.770
#   keyword-hit:              mean 0.883, min 0.333
#   tool-selection accuracy:  12/15 = 0.800
#
# Floors are deliberately set a notch below baseline so normal noise does
# not false-trip the gate.  Bump these UP (never silently down) when the
# pipeline genuinely improves.
GROUNDING_FLOOR = 0.55          # per-case; baseline min 0.620
GROUNDING_MEAN_FLOOR = 0.62     # aggregate; baseline mean 0.682
KEYWORD_FLOOR = 0.30            # per-case; baseline min 0.333
KEYWORD_MEAN_FLOOR = 0.75       # aggregate; baseline mean 0.883
TOOL_ACCURACY_FLOOR = 0.75      # aggregate; baseline 0.800

# Live LLM-judge metrics (AnswerRelevancy / Faithfulness / GEval) need an
# API key and cost money.  They only run when explicitly enabled.
RUN_LIVE_EVALS = os.environ.get("RUN_LIVE_EVALS", "").lower() in {
    "1",
    "true",
    "yes",
}
_HAS_LLM_KEY = bool(
    os.environ.get("OPENAI_API_KEY")
    and os.environ.get("OPENAI_API_KEY") not in {"dummy", "test-key-placeholder"}
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_CASES_PATH = PROJECT_ROOT / "data" / "eval_cases.json"


# ---------------------------------------------------------------------------
# Golden-set -> LLMTestCase bridge
# ---------------------------------------------------------------------------
def _load_golden_cases() -> List[Dict]:
    """Load the 20-case golden set from JSON."""
    with open(EVAL_CASES_PATH) as f:
        return json.load(f)


def _run_pipeline(query: str) -> Dict:
    """Run one query through the deterministic mock pipeline.

    Using the mock (the same one ``scripts/eval_harness.py`` ships) keeps
    the default CI path free of API keys and network calls while still
    exercising real scoring logic on real response/context text.
    """
    runner = MockPipelineRunner()
    return asyncio.run(runner.run(query))


def _build_test_cases() -> List[LLMTestCase]:
    """Materialize every golden case as a DeepEval ``LLMTestCase``.

    The pipeline output (response + retrieved contexts + tool called) is
    attached so both offline custom metrics and the optional live-judge
    metrics can read from a single test-case object.
    """
    cases = []
    for c in _load_golden_cases():
        out = _run_pipeline(c["query"])
        tool_called = out.get("tool_called")
        cases.append(
            LLMTestCase(
                input=c["query"],
                actual_output=out.get("response", ""),
                retrieval_context=out.get("contexts", []),
                context=out.get("contexts", []),
                # expected_output is only meaningful for the live judge;
                # we synthesize it from the golden keywords.
                expected_output=", ".join(c.get("expected_keywords", [])),
                # Tool tracking lives in metadata rather than the native
                # tools_called/expected_tools fields, which require typed
                # ToolCall objects we don't need for offline gating.
                metadata={
                    "id": c["id"],
                    "category": c["category"],
                    "expected_keywords": c.get("expected_keywords", []),
                    "expected_tool": c.get("expected_tool"),
                    "tool_called": tool_called,
                },
            )
        )
    return cases


# Build once at import time -- the mock pipeline is deterministic and cheap.
_GOLDEN_TEST_CASES = _build_test_cases()


# ---------------------------------------------------------------------------
# Custom offline metrics (NO external API calls)
# ---------------------------------------------------------------------------
class HallucinationGroundingMetric(BaseMetric):
    """Wrap the repo's 3-tier hallucination detector as a DeepEval metric.

    The detector scores how well a response is grounded in its retrieved
    context using token overlap + semantic similarity + source attribution
    (see ``app/validation/hallucination.py``).  Higher is better/safer.

    This is the *headline* offline gate: it runs with zero external API
    calls, so it protects CI on every PR regardless of secrets.
    """

    def __init__(self, threshold: float = GROUNDING_FLOOR):
        self.threshold = threshold
        self.async_mode = False
        self.include_reason = True
        self._detector = HallucinationDetector()

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        contexts = test_case.retrieval_context or test_case.context or []
        result = self._detector.score_response(
            test_case.actual_output or "", contexts
        )
        self.score = float(result.overall_score)
        self.success = self.score >= self.threshold
        self.reason = (
            f"grounding={self.score:.3f} level={result.level.value} "  # noqa: E231
            f"(threshold={self.threshold:.2f})"  # noqa: E231
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "Hallucination Grounding (offline)"


class KeywordCoverageMetric(BaseMetric):
    """Fraction of the golden expected-keywords present in the response.

    A deterministic, offline proxy for answer relevancy / completeness.
    """

    def __init__(self, threshold: float = KEYWORD_FLOOR):
        self.threshold = threshold
        self.async_mode = False
        self.include_reason = True

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        keywords = (test_case.metadata or {}).get("expected_keywords", [])
        text = (test_case.actual_output or "").lower()
        if not keywords:
            self.score = 1.0
        else:
            hits = sum(1 for kw in keywords if kw.lower() in text)
            self.score = hits / len(keywords)
        self.success = self.score >= self.threshold
        self.reason = (
            f"keyword coverage={self.score:.2f} "  # noqa: E231
            f"(threshold={self.threshold:.2f})"  # noqa: E231
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self):
        return "Keyword Coverage (offline)"


# ---------------------------------------------------------------------------
# Offline per-case gate (runs in default CI, no API key)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "test_case",
    _GOLDEN_TEST_CASES,
    ids=[f"case-{tc.metadata['id']}" for tc in _GOLDEN_TEST_CASES],
)
def test_offline_grounding_and_keywords(test_case: LLMTestCase):
    """Per-case offline gate: grounding + keyword coverage.

    Uses ``assert_test`` so failures surface through DeepEval's reporting
    the same way live-judge metrics would.  No external API calls.
    """
    assert_test(
        test_case,
        [
            HallucinationGroundingMetric(),
            KeywordCoverageMetric(),
        ],
    )


# ---------------------------------------------------------------------------
# Offline aggregate gates (catch broad regressions the per-case gate misses)
# ---------------------------------------------------------------------------
def test_offline_mean_grounding_gate():
    """Aggregate grounding must stay above the calibrated floor."""
    detector = HallucinationDetector()
    scores = [
        detector.score_response(
            tc.actual_output or "",
            tc.retrieval_context or tc.context or [],
        ).overall_score
        for tc in _GOLDEN_TEST_CASES
    ]
    mean_score = statistics.mean(scores)
    assert mean_score >= GROUNDING_MEAN_FLOOR, (
        f"Mean grounding {mean_score:.4f} regressed below floor "  # noqa: E231
        f"{GROUNDING_MEAN_FLOOR} (baseline ~0.682)"
    )


def test_offline_mean_keyword_gate():
    """Aggregate keyword coverage must stay above the calibrated floor."""
    coverages = []
    for tc in _GOLDEN_TEST_CASES:
        keywords = (tc.metadata or {}).get("expected_keywords", [])
        text = (tc.actual_output or "").lower()
        if not keywords:
            coverages.append(1.0)
        else:
            hits = sum(1 for kw in keywords if kw.lower() in text)
            coverages.append(hits / len(keywords))
    mean_cov = statistics.mean(coverages)
    assert mean_cov >= KEYWORD_MEAN_FLOOR, (
        f"Mean keyword coverage {mean_cov:.4f} regressed below floor "  # noqa: E231
        f"{KEYWORD_MEAN_FLOOR} (baseline ~0.883)"
    )


def test_offline_tool_selection_gate():
    """Tool-selection accuracy over tool-use cases must stay above floor."""
    correct = 0
    total = 0
    for tc in _GOLDEN_TEST_CASES:
        expected = (tc.metadata or {}).get("expected_tool")
        if not expected:
            continue
        total += 1
        actual = (tc.metadata or {}).get("tool_called")
        if actual == expected:
            correct += 1
    accuracy = correct / total if total else 1.0
    assert accuracy >= TOOL_ACCURACY_FLOOR, (
        f"Tool-selection accuracy {accuracy:.4f} ({correct}/{total}) "  # noqa: E231
        f"regressed below floor {TOOL_ACCURACY_FLOOR} (baseline 0.800)"
    )


# ---------------------------------------------------------------------------
# Optional live LLM-judge gate (opt-in, needs OPENAI_API_KEY)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not (RUN_LIVE_EVALS and _HAS_LLM_KEY),
    reason=(
        "Live LLM-judge evals disabled. Set RUN_LIVE_EVALS=1 and a real "
        "OPENAI_API_KEY to run AnswerRelevancy + Faithfulness."
    ),
)
@pytest.mark.parametrize(
    "test_case",
    _GOLDEN_TEST_CASES,
    ids=[f"case-{tc.metadata['id']}" for tc in _GOLDEN_TEST_CASES],
)
def test_live_llm_judge(test_case: LLMTestCase):
    """LLM-as-judge gate: AnswerRelevancy + Faithfulness.

    Opt-in only. These metrics call an external LLM judge, so they are
    excluded from the default (secret-free) CI path.
    """
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
    )

    assert_test(
        test_case,
        [
            AnswerRelevancyMetric(threshold=0.5),
            FaithfulnessMetric(threshold=0.5),
        ],
    )
