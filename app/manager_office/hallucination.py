"""
Hallucination Mitigation with Confidence Scoring
=================================================

Scores LLM responses against RAG contexts to detect potential hallucinations.
Uses token overlap, semantic similarity, and sentence-level source attribution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from prometheus_client import Counter, Histogram

from ..cctv.logging_utils import logger

# Prometheus metrics
RESPONSE_CONFIDENCE = Histogram(
    "mrc_response_confidence",
    "Confidence score of LLM responses",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)
HALLUCINATIONS_DETECTED = Counter(
    "mrc_hallucinations_detected",
    "Responses flagged as low confidence",
    ["level"],
)


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ConfidenceResult:
    overall_score: float
    level: ConfidenceLevel
    context_overlap_score: float
    semantic_similarity_score: float
    source_attribution_score: float

    def to_dict(self) -> Dict:
        return {
            "overall_score": round(self.overall_score, 4),
            "level": self.level.value,
            "context_overlap_score": round(self.context_overlap_score, 4),
            "semantic_similarity_score": round(self.semantic_similarity_score, 4),
            "source_attribution_score": round(self.source_attribution_score, 4),
        }


def _tokenize(text: str) -> set[str]:
    """Simple whitespace + lowercase tokenizer."""
    return set(re.findall(r"\w+", text.lower()))


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if len(s.split()) >= 3]


class HallucinationDetector:
    def __init__(
        self,
        high_threshold: float = 0.7,
        medium_threshold: float = 0.4,
    ):
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self._model = None  # lazy-loaded SentenceTransformer

    def _get_model(self):
        """Lazy load the sentence transformer model (same one used by RAG)."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                logger.warning(
                    "sentence-transformers not available for hallucination detection"
                )
        return self._model

    def _compute_context_overlap(
        self, response_text: str, contexts: List[str]
    ) -> float:
        """Token-level intersection ratio between response and contexts."""
        if not contexts:
            return 0.0

        response_tokens = _tokenize(response_text)
        if not response_tokens:
            return 0.0

        context_tokens = set()
        for ctx in contexts:
            context_tokens.update(_tokenize(ctx))

        overlap = response_tokens & context_tokens
        return len(overlap) / len(response_tokens)

    def _compute_semantic_similarity(
        self, response_text: str, contexts: List[str]
    ) -> float:
        """Cosine similarity between response and context embeddings."""
        model = self._get_model()
        if model is None or not contexts:
            return 0.0

        try:
            import numpy as np

            resp_emb = model.encode([response_text])[0]
            ctx_emb = model.encode(contexts)

            similarities = []
            for emb in ctx_emb:
                cos_sim = float(
                    np.dot(resp_emb, emb)
                    / (np.linalg.norm(resp_emb) * np.linalg.norm(emb) + 1e-10)
                )
                similarities.append(cos_sim)

            return max(similarities) if similarities else 0.0
        except Exception as e:
            logger.warning(f"Semantic similarity computation failed: {e}")
            return 0.0

    def _compute_source_attribution(
        self, response_text: str, contexts: List[str]
    ) -> float:
        """Sentence-level grounding: what fraction of response sentences are grounded in context."""
        if not contexts:
            return 0.0

        sentences = _split_sentences(response_text)
        if not sentences:
            return 0.0

        context_tokens = set()
        for ctx in contexts:
            context_tokens.update(_tokenize(ctx))

        grounded = 0
        for sentence in sentences:
            sent_tokens = _tokenize(sentence)
            if not sent_tokens:
                continue
            overlap_ratio = len(sent_tokens & context_tokens) / len(sent_tokens)
            if overlap_ratio >= 0.3:
                grounded += 1

        return grounded / len(sentences)

    def score_response(
        self,
        response_text: str,
        rag_contexts: List[str],
        user_query: str,
    ) -> ConfidenceResult:
        """Score a response for hallucination risk.

        Weights: 30% overlap + 50% semantic similarity + 20% source attribution
        """
        overlap = self._compute_context_overlap(response_text, rag_contexts)
        semantic = self._compute_semantic_similarity(response_text, rag_contexts)
        attribution = self._compute_source_attribution(response_text, rag_contexts)

        overall = 0.3 * overlap + 0.5 * semantic + 0.2 * attribution

        if overall >= self.high_threshold:
            level = ConfidenceLevel.HIGH
        elif overall >= self.medium_threshold:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        # Record metrics
        RESPONSE_CONFIDENCE.observe(overall)
        HALLUCINATIONS_DETECTED.labels(level=level.value).inc()

        logger.info(
            f"Confidence score: {overall:.3f} ({level.value}) "  # noqa: E231
            f"[overlap={overlap:.3f}, semantic={semantic:.3f}, "  # noqa: E231
            f"attribution={attribution:.3f}]"  # noqa: E231
        )

        return ConfidenceResult(
            overall_score=overall,
            level=level,
            context_overlap_score=overlap,
            semantic_similarity_score=semantic,
            source_attribution_score=attribution,
        )
