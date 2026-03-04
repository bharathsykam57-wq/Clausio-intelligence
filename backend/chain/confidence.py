"""
chain/confidence.py  ★ NEW in v2
Calculates answer confidence from retrieval scores.

THREE LEVELS:
  HIGH   (score > 0.80) — Strong matches found. Answer is likely accurate.
  MEDIUM (score 0.60–0.80) — Reasonable matches. Answer may be incomplete.
  LOW    (score < 0.60) — Weak matches. Answer may be unreliable.

WHY THIS MATTERS FOR USERS:
  Legal professionals need to know when to verify an answer independently.
  Showing confidence signals that LexIA is honest about its limitations.
  This is what separates a trustworthy legal tool from a confident hallucinator.

HOW SCORE IS CALCULATED:
  Uses rerank_score if available (more reliable), falls back to similarity.
  Takes weighted average: top chunk gets 50% weight, others share 50%.
  This reflects that the best chunk usually drives answer quality.
"""
from dataclasses import dataclass


@dataclass
class ConfidenceResult:
    level: str        # "HIGH" | "MEDIUM" | "LOW"
    score: float      # 0.0 to 1.0
    message: str      # Human-readable explanation


def calculate_confidence(chunks: list[dict]) -> ConfidenceResult:
    """
    Calculate confidence level from retrieved chunks.

    Args:
        chunks: Retrieved chunks with similarity/rerank_score

    Returns:
        ConfidenceResult with level, score, and user-facing message
    """
    if not chunks:
        return ConfidenceResult(
            level="LOW",
            score=0.0,
            message="No relevant passages found in the knowledge base.",
        )

    # Use rerank_score if available (post-reranking), else similarity (pre-reranking)
    raw_scores = [c.get("rerank_score", c.get("similarity", 0.0)) for c in chunks]

    # Normalize rerank scores to 0-1 range (cross-encoder outputs can be > 1)
    max_score = max(raw_scores)
    if max_score > 1.0:
        raw_scores = [s / (max_score + 1e-8) for s in raw_scores]

    # Weighted average: top chunk = 50%, rest split remaining 50%
    if len(raw_scores) == 1:
        score = raw_scores[0]
    else:
        top_weight = 0.5
        rest_weight = 0.5 / (len(raw_scores) - 1)
        score = raw_scores[0] * top_weight + sum(s * rest_weight for s in raw_scores[1:])

    score = round(min(max(score, 0.0), 1.0), 3)

    if score >= 0.80:
        return ConfidenceResult(
            level="HIGH",
            score=score,
            message="Strong match found in the knowledge base.",
        )
    elif score >= 0.60:
        return ConfidenceResult(
            level="MEDIUM",
            score=score,
            message="Partial match. Answer may be incomplete — verify with source documents.",
        )
    else:
        return ConfidenceResult(
            level="LOW",
            score=score,
            message="Weak match. This answer may be unreliable. Consult original documents.",
        )
