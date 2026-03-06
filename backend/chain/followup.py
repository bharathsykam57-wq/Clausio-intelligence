"""
chain/followup.py 
Generates follow-up question suggestions grounded in retrieved chunks.

WHY GROUNDED FOLLOW-UPS?
  Generic follow-ups ("Tell me more") add no value.
  Grounded follow-ups ("What are the fines for violating Article 10?")
  guide users deeper into the knowledge base naturally.

IMPORTANT CONSTRAINT:
  Follow-ups must be answerable from the knowledge base.
  We pass the retrieved chunks to the prompt to force grounding.
  Without this constraint, the LLM suggests questions it can't answer.

ONLY SHOW FOR MEDIUM+ CONFIDENCE:
  Low confidence = the current answer is unreliable.
  Suggesting follow-ups on an unreliable answer misleads users.
  Gate on MEDIUM+ to ensure follow-ups have a reasonable chance of being answered.
"""
from mistralai import Mistral
from loguru import logger
from config import get_settings

settings = get_settings()
client = Mistral(api_key=settings.mistral_api_key)

FOLLOWUP_SYSTEM = """You are a legal research assistant.
Based on the document excerpts and the question just answered, suggest exactly 3 follow-up
questions the user might want to ask next.

Rules:
- Each question must be answerable from the EU AI Act or GDPR/RGPD (the knowledge base)
- Questions should go deeper, not broader
- Keep each question under 15 words
- Match the language of the original question (French → French, English → English)

Reply with ONLY the 3 questions, one per line. No numbering, no bullets."""


def generate_followups(query: str, chunks: list[dict], confidence_level: str) -> list[str]:
    """
    Generate 3 follow-up questions grounded in retrieved chunks.

    Args:
        query: Original user question
        chunks: Retrieved chunks (used to ground follow-ups)
        confidence_level: "HIGH" | "MEDIUM" | "LOW"

    Returns:
        List of 3 follow-up question strings, or [] if confidence is LOW
    """
    # Don't suggest follow-ups when confidence is low — they'll be unreliable
    if confidence_level == "LOW":
        return []

    if not chunks:
        return []

    # Build a brief context summary for the prompt
    context_preview = "\n\n".join(
        f"[{c.get('metadata', {}).get('title', 'Document')}]: {c['content'][:200]}..."
        for c in chunks[:3]
    )

    try:
        response = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": FOLLOWUP_SYSTEM},
                {"role": "user", "content": f"Question answered: {query}\n\nRelevant excerpts:\n{context_preview}\n\nSuggest 3 follow-up questions:"},
            ],
            temperature=0.4,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        questions = [q.strip() for q in raw.split("\n") if q.strip() and len(q.strip()) > 10]
        return questions[:3]  # Ensure max 3
    except Exception as e:
        logger.warning(f"Follow-up generation failed: {e}")
        return []
