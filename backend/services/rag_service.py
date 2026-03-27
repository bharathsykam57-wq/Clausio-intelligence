# pyre-ignore-all-errors
import time
import json
import logging
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_random_exponential, before_sleep_log

# Phase 2 Observability: Centralized JSON logger
from logger import get_structured_logger
log = get_structured_logger("rag_service")

from cache.redis_cache import get_cached_response, set_cached_response

# Domain components needed for RAG pipeline orchestration
from mistralai import Mistral
from retrieval.query_router import classify_query, QueryType, OUT_OF_SCOPE_RESPONSE
from retrieval.retriever import retrieve
from retrieval.hyde_retriever import hyde_retrieve
from ingest.embedder import embed_query
from chain.contradiction import check_contradictions
from chain.confidence import calculate_confidence
from chain.followup import generate_followups
from chain.rag_chain import format_context, extract_sources, SYSTEM_PROMPT, RAG_TEMPLATE
from config import get_settings

settings = get_settings()
client = Mistral(api_key=settings.mistral_api_key)

# Phase 6: Implement explicit LLM retries with exponential backoff & jitter
@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=10),
    before_sleep=before_sleep_log(logging.getLogger("rag_service"), logging.WARNING),
    reraise=True
)
def _generate_llm_response_with_retry(messages: list) -> dict:
    """Executes Mistral LLM inference handling transient network 5xx timeouts."""
    return client.chat.complete(
        model=settings.mistral_chat_model,
        messages=messages,
        temperature=0.1,
        max_tokens=1500,
    )

def log_audit_request(db, user_id: str, question: str, result: dict, latency_ms: int):
    """Saves telemetry to postgres synchronously."""
    try:
        db.execute(text("""
            INSERT INTO request_logs (user_id, question, query_type, latency_ms, chunks_used, confidence, created_at)
            VALUES (:uid, :q, :qt, :lat, :cu, :conf, NOW())
        """), {"uid": user_id, "q": question[:500], "qt": result.get("query_type",""),  # type: ignore
               "lat": latency_ms, "cu": result.get("chunks_used",0),
               "conf": result.get("confidence",{}).get("level","")})
        db.commit()
    except Exception as e:
        log.warning("Audit log postgres sync failed", extra={"structured_metadata": {"error": str(e)}})

def process_chat(question: str, history: list, filter_source: str | None, use_cache: bool):
    """
    Core RAG answering business logic with transparent caching and timing.
    Throws ValueError on RAG backend failure.
    Returns: (result_dict, latency_ms, is_cached)
    """
    clean_question = question.strip().lower()
    
    # Phase 4: Empty query fallback
    if not clean_question:
        log.warning("Empty query intercepted", extra={"structured_metadata": {"error_type": "empty_query", "failure_category": "user_error"}})
        return {"answer": "Please provide a valid question regarding the selected knowledge base.", "sources": [], "chunks_used": 0, "query_type": "UNKNOWN", "confidence": {"level": "LOW", "score": 0.0, "message": "Empty query"}, "contradiction": {"has_contradiction": False, "explanation": "", "checked": False}, "follow_up_questions": []}, 0, False

    # Phase 4: Long query fallback
    if len(question) > 2000:
        log.warning("Query too long", extra={"structured_metadata": {"error_type": "long_query", "failure_category": "user_error", "query_length_chars": len(question)}})
        return {"answer": "Your question is too long. Please shorten it to under 2000 characters.", "sources": [], "chunks_used": 0, "query_type": "UNKNOWN", "confidence": {"level": "LOW", "score": 0.0, "message": "Query exceeded length limit"}, "contradiction": {"has_contradiction": False, "explanation": "", "checked": False}, "follow_up_questions": []}, 0, False

    if use_cache and not history:
        cached = get_cached_response(clean_question)
        if cached:
            log.info("Cache hit", extra={"structured_metadata": {"query": question[:100], "cached": True}})  # type: ignore
            return {**cached, "cached": True}, 0, True

    start_total = time.perf_counter()
    metrics = {}
    
    try:
        # Step 1: Route query
        query_type = classify_query(question)
        
        if query_type == QueryType.OUT_OF_SCOPE:
            log.info("Out of scope query", extra={"structured_metadata": {"error_type": "irrelevant_query", "failure_category": "out_of_scope", "query_truncated": question[:100]}})  # type: ignore
            result = {
                "answer": OUT_OF_SCOPE_RESPONSE,
                "sources": [],
                "chunks_used": 0,
                "query_type": query_type.value,
                "confidence": {"level": "LOW", "score": 0.0, "message": "Question is outside the knowledge base."},
                "contradiction": {"has_contradiction": False, "explanation": "", "checked": False},
                "follow_up_questions": [],
            }
            return result, int((time.perf_counter() - start_total)*1000), False

        # Phase 2 Observability: Measure Embedding Explicitly
        t0 = time.perf_counter()
        query_vec = None
        if query_type == QueryType.SINGLE_CHUNK:
            query_vec = embed_query(question)
            metrics["latency_embedding_ms"] = int((time.perf_counter() - t0) * 1000)

        # Phase 2 Observability: Measure Retrieval
        t1 = time.perf_counter()
        if query_type == QueryType.MULTI_HOP:
            # Note: HyDE retrieval handles embedding internally natively.
            chunks = hyde_retrieve(question, top_k=settings.retrieval_top_k, filter_source=filter_source)
        else:
            chunks = retrieve(question, filter_source=filter_source, query_embedding=query_vec)
        metrics["latency_retrieval_ms"] = int((time.perf_counter() - t1) * 1000)

        # Triggers empty retrieval error log case
        if not chunks:
            log.warning("Empty retrieval case", extra={"structured_metadata": {
                "query_truncated": question[:100],  # type: ignore
                "query_type": query_type.value,
                "latency_retrieval_ms": metrics.get("latency_retrieval_ms", 0),
                "error_type": "empty_retrieval",
                "failure_category": "model_failure"
            }})
            result = {
                "answer": "No relevant information found in the knowledge base for this question.",
                "sources": [],
                "chunks_used": 0,
                "query_type": query_type.value,
                "confidence": {"level": "LOW", "score": 0.0, "message": "No matches found."},
                "contradiction": {"has_contradiction": False, "explanation": "", "checked": False},
                "follow_up_questions": [],
            }
            return result, int((time.perf_counter() - start_total)*1000), False

        contradiction = check_contradictions(chunks)
        confidence_result = calculate_confidence(chunks)

        # Phase 2 Observability: Measure LLM Generation
        t2 = time.perf_counter()
        context = format_context(chunks)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-6:])  # type: ignore
        messages.append({"role": "user", "content": RAG_TEMPLATE.format(context=context, question=question)})

        try:
            response = _generate_llm_response_with_retry(messages)
            answer_text = response.choices[0].message.content
            
            # Phase 2 Observability: Measure Token Usage natively
            if hasattr(response, "usage") and response.usage:
                metrics["tokens_prompt"] = response.usage.prompt_tokens
                metrics["tokens_completion"] = response.usage.completion_tokens
                metrics["tokens_total"] = response.usage.total_tokens
                
        except Exception as e:
            log.error("Generation failure", extra={"structured_metadata": {
                "query_truncated": question[:100],  # type: ignore
                "error_type": "generation_failure",
                "failure_category": "model_failure",
                "error_message": str(e)
            }})
            raise e

        metrics["latency_generation_ms"] = int((time.perf_counter() - t2) * 1000)

        # Phase 4: Low confidence fallback intervention
        if confidence_result.level == "LOW" and chunks:
            log.warning("Low confidence response generated", extra={"structured_metadata": {
                "error_type": "low_confidence",
                "failure_category": "model_failure",
                "score": confidence_result.score,
                "threshold": 0.4,
                "query_truncated": question[:100]  # type: ignore
            }})
            answer_text = "I am not highly confident in this answer given the available context, but here is what I found: \n\n" + answer_text

        follow_ups = generate_followups(question, chunks, confidence_result.level)

        result = {
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

        latency_total_ms = int((time.perf_counter() - start_total) * 1000)
        metrics["latency_total_ms"] = latency_total_ms
        
        # Core structured RAG audit log
        log.info("RAG Request Compiled", extra={"structured_metadata": {
            "query_truncated": question[:100],  # type: ignore
            "query_length_chars": len(question),
            "query_type": query_type.value,
            "chunks_used": len(chunks),
            "response_length_chars": len(answer_text),
            "confidence_level": confidence_result.level,
            "confidence_score": confidence_result.score,
            "latencies": metrics,
        }})

        result["cached"] = False
        
        if use_cache and not history:
            set_cached_response(clean_question, result)
            
        return result, latency_total_ms, False

    except Exception as e:
        latency_total_ms = int((time.perf_counter() - start_total) * 1000)
        log.error("RAG pipeline unhandled crash", extra={"structured_metadata": {
             "query_truncated": question[:100],  # type: ignore
             "latency_total_ms": latency_total_ms,
             "error_type": "pipeline_crash",
             "failure_category": "model_failure",
             "error": str(e)
        }})
        raise ValueError("Failed to generate answer via LLM") from e
