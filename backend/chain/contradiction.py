"""
chain/contradiction.py  ★ NEW in v2
Detects conflicting information across retrieved chunks.

THE PROBLEM:
  When the EU AI Act and RGPD overlap (e.g. data processing for AI systems),
  retrieved chunks from different documents can give different answers.
  Without detection, the LLM silently picks one version — misleading the user.

THE SOLUTION:
  Check if retrieved chunks contradict each other.
  If yes, surface the conflict to the user instead of hiding it.
  This is honest AI behavior — a major differentiator vs generic chatbots.

OPTIMIZATION:
  Only check when top chunks have similar similarity scores (within 0.05).
  Closely-scored chunks from different sources = higher contradiction risk.
  This avoids the extra LLM call for clear-cut single-source answers.

PORTFOLIO SIGNAL: Shows you thought about edge cases, not just happy path.
"""
from mistralai import Mistral
from loguru import logger
from config import get_settings

settings = get_settings()
client = Mistral(api_key=settings.mistral_api_key)

CONTRADICTION_SYSTEM = """You are a legal document analyst.
Given multiple excerpts from legal documents, determine if any of them
contain conflicting or contradictory information on the same topic.

Reply in this exact format:
VERDICT: YES or NO
EXPLANATION: One sentence explaining what conflicts (if YES) or why they are consistent (if NO).

Be conservative — only flag genuine contradictions, not different perspectives on different topics."""


def check_contradictions(chunks: list[dict]) -> dict:
    """
    Check if retrieved chunks contain contradictory information.

    Args:
        chunks: List of retrieved chunks with content and metadata

    Returns:
        {
          "has_contradiction": bool,
          "explanation": str,
          "checked": bool  # False if check was skipped
        }
    """
    if len(chunks) < 2:
        return {"has_contradiction": False, "explanation": "", "checked": False}

    # Only check when scores are close (contradiction risk is higher)
    scores = [c.get("rerank_score", c.get("similarity", 0)) for c in chunks]
    score_range = max(scores) - min(scores) if scores else 1.0

    if score_range > 0.15:
        # Scores are spread out — top chunk is clearly best, skip check
        return {"has_contradiction": False, "explanation": "", "checked": False}

    # Check sources — only meaningful if chunks come from different documents
    sources = set(c.get("metadata", {}).get("source", "") for c in chunks)
    if len(sources) < 2:
        return {"has_contradiction": False, "explanation": "", "checked": False}

    # Build context for contradiction check
    context_parts = []
    for i, chunk in enumerate(chunks[:4], 1):  # Max 4 chunks to keep prompt short
        meta = chunk.get("metadata", {})
        title = meta.get("title", meta.get("source", "Unknown"))
        context_parts.append(f"[Excerpt {i} from {title}]\n{chunk['content'][:400]}")

    context = "\n\n---\n\n".join(context_parts)

    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": CONTRADICTION_SYSTEM},
                {"role": "user", "content": f"Excerpts to analyze:\n\n{context}"},
            ],
            temperature=0.0,
            max_tokens=100,
        )
        raw = response.choices[0].message.content.strip()
        lines = raw.split("\n")

        has_contradiction = False
        explanation = ""
        for line in lines:
            if line.startswith("VERDICT:"):
                has_contradiction = "YES" in line.upper()
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()

        if has_contradiction:
            logger.info(f"Contradiction detected: {explanation}")

        return {"has_contradiction": has_contradiction, "explanation": explanation, "checked": True}

    except Exception as e:
        logger.warning(f"Contradiction check failed: {e}")
        return {"has_contradiction": False, "explanation": "", "checked": False}
