"""
chain/rag_chain.py
Master RAG orchestration — ties all components together.

PIPELINE FOR EACH QUERY:
  1. Classify query type (router)
  2. If OUT_OF_SCOPE → return immediately, no LLM call
  3. If MULTI_HOP → use HyDE retrieval
  4. If SINGLE_CHUNK → use standard retrieval
  5. Check for contradictions in retrieved chunks
  6. Calculate confidence score
  7. Generate answer with Mistral (grounded in context)
  8. Generate follow-up suggestions
  9. Return everything

DESIGN DECISION — Why not LangChain for this?
  LangChain's abstractions are great for prototypes but hurt debuggability
  in production. When retrieval quality degrades, raw API calls make it
  trivial to log and inspect every step. We use LangChain only for
  text splitting and embedding wrappers where it adds clear value.
"""
from mistralai import Mistral
from loguru import logger
from retrieval.query_router import classify_query, QueryType, OUT_OF_SCOPE_RESPONSE
from retrieval.retriever import retrieve
from retrieval.hyde_retriever import hyde_retrieve
from chain.contradiction import check_contradictions
from chain.confidence import calculate_confidence
from chain.followup import generate_followups
from config import get_settings

settings = get_settings()
client = Mistral(api_key=settings.mistral_api_key)

SYSTEM_PROMPT = """You are LexIA, an expert legal AI assistant specializing in EU digital regulation.
Your knowledge covers the EU Artificial Intelligence Act and GDPR/RGPD.

RULES (follow strictly):
1. Answer ONLY from the provided context — never from prior knowledge
2. Cite sources inline: [Source: <title>, Page <page>]
3. If context is insufficient, say: "The provided excerpts don't contain enough information to answer this fully."
4. Match the user's language (French question → French answer)
5. Be precise. Your audience is legal and technical professionals.
6. Structure long answers with clear sections."""

RAG_TEMPLATE = """Relevant excerpts from the knowledge base:

{context}

---

Question: {question}

Answer with inline citations [Source: <title>, Page <page>]."""


def format_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        title = meta.get("title", meta.get("source", "Unknown"))
        page = meta.get("page", "?")
        score = chunk.get("rerank_score", chunk.get("similarity", 0))
        parts.append(f"[Excerpt {i} | {title} | Page {page} | score: {score:.3f}]\n{chunk['content'].strip()}")
    return "\n\n---\n\n".join(parts)


def extract_sources(chunks: list[dict]) -> list[dict]:
    sources, seen = [], set()
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        key = (meta.get("title", ""), meta.get("page", ""))
        if key not in seen:
            seen.add(key)
            sources.append({
                "title": meta.get("title", meta.get("source", "Unknown")),
                "page": meta.get("page"),
                "source_key": meta.get("source"),
                "url": meta.get("url"),
                "similarity": round(chunk.get("rerank_score", chunk.get("similarity", 0)), 3),
            })
    return sources


def answer(question: str, history: list[dict] | None = None, filter_source: str | None = None) -> dict:
    """
    Full RAG pipeline. Returns answer + all enrichment signals.

    Returns:
        {
          answer: str,
          sources: list[dict],
          chunks_used: int,
          query_type: str,
          confidence: {level, score, message},
          contradiction: {has_contradiction, explanation, checked},
          follow_up_questions: list[str],
        }
    """
    history = history or []

    # Step 1: Classify query
    query_type = classify_query(question)

    # Step 2: Handle out-of-scope immediately
    if query_type == QueryType.OUT_OF_SCOPE:
        return {
            "answer": OUT_OF_SCOPE_RESPONSE,
            "sources": [],
            "chunks_used": 0,
            "query_type": query_type.value,
            "confidence": {"level": "LOW", "score": 0.0, "message": "Question is outside the knowledge base."},
            "contradiction": {"has_contradiction": False, "explanation": "", "checked": False},
            "follow_up_questions": [],
        }

    # Step 3: Retrieve (HyDE for multi-hop, standard for single-chunk)
    if query_type == QueryType.MULTI_HOP:
        logger.info("Using HyDE retrieval for multi-hop query")
        chunks = hyde_retrieve(question, top_k=settings.retrieval_top_k, filter_source=filter_source)
    else:
        chunks = retrieve(question, filter_source=filter_source)

    if not chunks:
        return {
            "answer": "No relevant information found in the knowledge base for this question.",
            "sources": [],
            "chunks_used": 0,
            "query_type": query_type.value,
            "confidence": {"level": "LOW", "score": 0.0, "message": "No matches found."},
            "contradiction": {"has_contradiction": False, "explanation": "", "checked": False},
            "follow_up_questions": [],
        }

    # Step 4: Contradiction check
    contradiction = check_contradictions(chunks)

    # Step 5: Confidence score
    confidence_result = calculate_confidence(chunks)

    # Step 6: Generate answer
    context = format_context(chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": RAG_TEMPLATE.format(context=context, question=question)})

    response = client.chat.complete(
        model=settings.mistral_chat_model,
        messages=messages,
        temperature=0.1,
        max_tokens=1500,
    )
    answer_text = response.choices[0].message.content

    # Step 7: Follow-up suggestions
    follow_ups = generate_followups(question, chunks, confidence_result.level)

    return {
        "answer": answer_text,
        "sources": extract_sources(chunks),
        "chunks_used": len(chunks),
        "query_type": query_type.value,
        "confidence": {
            "level": confidence_result.level,
            "score": confidence_result.score,
            "message": confidence_result.message,
        },
        "contradiction": {
            "has_contradiction": contradiction["has_contradiction"],
            "explanation": contradiction["explanation"],
            "checked": contradiction["checked"],
        },
        "follow_up_questions": follow_ups,
    }


async def answer_stream(question: str, history: list[dict] | None = None, filter_source: str | None = None):
    """
    Streaming version. Yields tokens then a final JSON metadata event.
    Format:
      data: <token>          — text tokens
      event: metadata        — final JSON with sources, confidence, etc.
      event: done            — stream complete
    """
    import json
    history = history or []

    query_type = classify_query(question)

    if query_type == QueryType.OUT_OF_SCOPE:
        yield OUT_OF_SCOPE_RESPONSE
        meta = {
            "sources": [], "query_type": query_type.value, "chunks_used": 0,
            "confidence": {"level": "LOW", "score": 0.0, "message": "Out of scope."},
            "contradiction": {"has_contradiction": False, "explanation": "", "checked": False},
            "follow_up_questions": [],
        }
        yield f"\n[[METADATA]]{json.dumps(meta)}"
        return

    if query_type == QueryType.MULTI_HOP:
        chunks = hyde_retrieve(question, top_k=settings.retrieval_top_k, filter_source=filter_source)
    else:
        chunks = retrieve(question, filter_source=filter_source)

    if not chunks:
        yield "No relevant information found in the knowledge base."
        yield f"\n[[METADATA]]{json.dumps({'sources': [], 'query_type': query_type.value, 'chunks_used': 0, 'confidence': {'level': 'LOW', 'score': 0.0, 'message': 'No matches.'}, 'contradiction': {'has_contradiction': False, 'explanation': '', 'checked': False}, 'follow_up_questions': []})}"
        return

    contradiction = check_contradictions(chunks)
    confidence_result = calculate_confidence(chunks)

    context = format_context(chunks)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-6:])
    messages.append({"role": "user", "content": RAG_TEMPLATE.format(context=context, question=question)})

    stream = client.chat.stream(
        model=settings.mistral_chat_model,
        messages=messages,
        temperature=0.1,
        max_tokens=1500,
    )
    for event in stream:
        delta = event.data.choices[0].delta.content
        if delta:
            yield delta

    follow_ups = generate_followups(question, chunks, confidence_result.level)

    meta = {
        "sources": extract_sources(chunks),
        "query_type": query_type.value,
        "chunks_used": len(chunks),
        "confidence": {
            "level": confidence_result.level,
            "score": confidence_result.score,
            "message": confidence_result.message,
        },
        "contradiction": {
            "has_contradiction": contradiction["has_contradiction"],
            "explanation": contradiction["explanation"],
            "checked": contradiction["checked"],
        },
        "follow_up_questions": follow_ups,
    }
    yield f"\n[[METADATA]]{json.dumps(meta)}"
