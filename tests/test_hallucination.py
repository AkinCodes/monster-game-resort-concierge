"""Tests for hallucination detection and confidence scoring."""

import pytest
from app.manager_office.hallucination import (
    HallucinationDetector,
    ConfidenceLevel,
    _tokenize,
    _split_sentences,
)


@pytest.fixture
def detector():
    return HallucinationDetector(high_threshold=0.7, medium_threshold=0.4)


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World! Test 123")
        assert "hello" in tokens
        assert "world" in tokens
        assert "123" in tokens

    def test_empty(self):
        assert _tokenize("") == set()


class TestSplitSentences:
    def test_basic(self):
        text = "First sentence here. Second sentence here. Third one too."
        sentences = _split_sentences(text)
        assert len(sentences) == 3

    def test_short_fragments_filtered(self):
        text = "Ok. This is a real sentence here."
        sentences = _split_sentences(text)
        assert len(sentences) == 1


class TestContextOverlap:
    def test_identical_text_high_overlap(self, detector):
        text = "The vampire manor has gothic architecture and dark hallways."
        contexts = [text]
        score = detector._compute_context_overlap(text, contexts)
        assert score == 1.0

    def test_unrelated_text_low_overlap(self, detector):
        text = (
            "Quantum physics explains particle behavior at subatomic scales."
        )
        contexts = [
            "The vampire manor has gothic architecture and dark hallways."
        ]
        score = detector._compute_context_overlap(text, contexts)
        assert score < 0.3

    def test_empty_contexts(self, detector):
        score = detector._compute_context_overlap("some text", [])
        assert score == 0.0


class TestSemanticSimilarity:
    def test_similar_text(self, detector):
        text = "The hotel has beautiful dark gothic rooms."
        contexts = ["The resort features gorgeous shadowy gothic chambers."]
        score = detector._compute_semantic_similarity(text, contexts)
        assert score > 0.5

    def test_unrelated_text(self, detector):
        text = "Python programming uses indentation for code blocks."
        contexts = [
            "The vampire manor has gothic architecture and dark hallways."
        ]
        score = detector._compute_semantic_similarity(text, contexts)
        assert score < 0.5

    def test_empty_contexts(self, detector):
        score = detector._compute_semantic_similarity("some text", [])
        assert score == 0.0


class TestSourceAttribution:
    def test_grounded_response(self, detector):
        contexts = [
            "The Vampire Manor features eternal night ambiance "
            "and gothic towers."
        ]
        response = (
            "The Vampire Manor features eternal night ambiance. "
            "It has gothic towers."
        )
        score = detector._compute_source_attribution(response, contexts)
        assert score > 0.5

    def test_ungrounded_response(self, detector):
        contexts = [
            "The Vampire Manor features eternal night ambiance "
            "and gothic towers."
        ]
        response = (
            "Quantum computers leverage superposition for parallel "
            "computation. Neural networks process data through "
            "layered architectures."
        )
        score = detector._compute_source_attribution(response, contexts)
        assert score < 0.3


class TestScoreResponse:
    def test_high_confidence_identical(self, detector):
        text = (
            "The Vampire Manor has dark gothic hallways "
            "and eternal night ambiance."
        )
        contexts = [text]
        result = detector.score_response(
            text, contexts, "Tell me about Vampire Manor"
        )
        assert result.level == ConfidenceLevel.HIGH
        assert result.overall_score >= 0.7

    def test_low_confidence_unrelated(self, detector):
        text = (
            "Quantum computing leverages superposition for parallel "
            "computation across multiple dimensions."
        )
        contexts = [
            "The Vampire Manor features eternal night ambiance "
            "and gothic towers."
        ]
        result = detector.score_response(
            text, contexts, "Tell me about Vampire Manor"
        )
        assert result.level == ConfidenceLevel.LOW
        assert result.overall_score < 0.4

    def test_result_to_dict(self, detector):
        text = "The resort has rooms."
        contexts = ["The resort has rooms and amenities."]
        result = detector.score_response(text, contexts, "rooms?")
        d = result.to_dict()
        assert "overall_score" in d
        assert "level" in d
        assert d["level"] in ["HIGH", "MEDIUM", "LOW"]

    def test_empty_contexts_returns_low(self, detector):
        result = detector.score_response("Some response", [], "query")
        assert result.level == ConfidenceLevel.LOW
