"""
tests/unit/test_confidence.py
Unit tests for confidence scoring logic.
No external dependencies needed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


class TestConfidenceScoring:
    def test_empty_chunks_returns_low(self):
        from chain.confidence import calculate_confidence
        result = calculate_confidence([])
        assert result.level == "LOW"
        assert result.score == 0.0

    def test_high_scores_return_high(self):
        from chain.confidence import calculate_confidence
        chunks = [
            {"rerank_score": 0.92},
            {"rerank_score": 0.88},
            {"rerank_score": 0.85},
        ]
        result = calculate_confidence(chunks)
        assert result.level == "HIGH"
        assert result.score >= 0.80

    def test_medium_scores_return_medium(self):
        from chain.confidence import calculate_confidence
        chunks = [
            {"rerank_score": 0.70},
            {"rerank_score": 0.65},
        ]
        result = calculate_confidence(chunks)
        assert result.level == "MEDIUM"

    def test_low_scores_return_low(self):
        from chain.confidence import calculate_confidence
        chunks = [{"similarity": 0.45}, {"similarity": 0.40}]
        result = calculate_confidence(chunks)
        assert result.level == "LOW"

    def test_single_chunk(self):
        from chain.confidence import calculate_confidence
        chunks = [{"rerank_score": 0.95}]
        result = calculate_confidence(chunks)
        assert result.level == "HIGH"

    def test_top_chunk_weighted_more(self):
        """Top chunk has 50% weight — verify it dominates the score."""
        from chain.confidence import calculate_confidence
        # High top chunk, low rest
        chunks_high_top = [{"rerank_score": 0.95}, {"rerank_score": 0.10}, {"rerank_score": 0.10}]
        # Low top chunk, high rest
        chunks_low_top  = [{"rerank_score": 0.10}, {"rerank_score": 0.10}, {"rerank_score": 0.10}]
        score_high = calculate_confidence(chunks_high_top).score
        score_low  = calculate_confidence(chunks_low_top).score
        assert score_high > score_low  # Top chunk matters more

    def test_score_bounded_0_to_1(self):
        from chain.confidence import calculate_confidence
        # Cross-encoder can return scores > 1
        chunks = [{"rerank_score": 5.0}, {"rerank_score": 4.0}]
        result = calculate_confidence(chunks)
        assert 0.0 <= result.score <= 1.0

    def test_uses_rerank_over_similarity(self):
        """When rerank_score is available, prefer it over similarity."""
        from chain.confidence import calculate_confidence
        chunks = [{"similarity": 0.3, "rerank_score": 0.9}]
        result = calculate_confidence(chunks)
        assert result.level == "HIGH"  # Uses rerank_score 0.9, not similarity 0.3
