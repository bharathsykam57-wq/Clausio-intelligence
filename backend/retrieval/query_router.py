"""
retrieval/query_router.py 
Query classification and routing.

THREE QUERY TYPES:
  SINGLE_CHUNK  — Answer lives in one document passage
                  Example: "Define 'AI system' under the EU AI Act"
                  Route: Standard retrieval, top_k=3

  MULTI_HOP     — Answer requires combining multiple passages
                  Example: "Compare GDPR consent requirements with AI Act obligations"
                  Route: HyDE retrieval, top_k=6 for broader context

  OUT_OF_SCOPE  — Answer not in the knowledge base
                  Example: "What is the French corporate tax rate?"
                  Route: Skip retrieval entirely, return clean message

WHY THIS MATTERS:
  Without routing, multi-hop questions get poor answers (not enough context).
  Without OOS detection, the model hallucinates confidently about topics
  outside the documents. Routing fixes both problems at the cost of one
  extra LLM call (~100ms).

PORTFOLIO SIGNAL: This shows you think about failure modes proactively,
  not just the happy path.
"""
from enum import Enum
from mistralai import Mistral
from loguru import logger
from config import get_settings

settings = get_settings()
client = Mistral(api_key=settings.mistral_api_key)


class QueryType(str, Enum):
    SINGLE_CHUNK = "SINGLE_CHUNK"
    MULTI_HOP = "MULTI_HOP"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


ROUTER_SYSTEM = """You are a query classifier for a legal RAG system.
The knowledge base contains ONLY: EU Artificial Intelligence Act and GDPR/RGPD.

Classify the query into exactly one of:
  SINGLE_CHUNK  — answerable from one passage in the knowledge base
  MULTI_HOP     — requires combining multiple passages from the knowledge base
  OUT_OF_SCOPE  — topic not covered in EU AI Act or GDPR/RGPD

Reply with ONLY the classification word. Nothing else.

Examples:
  "What is the definition of an AI system?" → SINGLE_CHUNK
  "How do GDPR data subject rights interact with AI Act requirements?" → MULTI_HOP
  "What is the French minimum wage?" → OUT_OF_SCOPE
  "List prohibited AI practices" → SINGLE_CHUNK
  "Compare obligations for providers vs deployers across both regulations" → MULTI_HOP
  "Who is the current French president?" → OUT_OF_SCOPE"""


def classify_query(query: str) -> QueryType:
    """
    Classify a query using the router LLM.
    Returns QueryType enum. Defaults to SINGLE_CHUNK on any error.
    """
    try:
        response = client.chat.complete(
            model="mistral-small-latest",   # Use small model for classification — cheaper + faster
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        raw = response.choices[0].message.content.strip().upper()
        query_type = QueryType(raw)
        logger.info(f"Query classified as: {query_type.value}")
        return query_type
    except Exception as e:
        logger.warning(f"Router failed ({e}), defaulting to SINGLE_CHUNK")
        return QueryType.SINGLE_CHUNK

# out-of-scope response to return when router classifies as OUT_OF_SCOPE
OUT_OF_SCOPE_RESPONSE = (
    "This question falls outside the knowledge base. "
    "LexIA only answers questions about the EU Artificial Intelligence Act and GDPR/RGPD. "
    "Please rephrase your question or ask about EU AI regulation or data protection law."
)
