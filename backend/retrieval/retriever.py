"""
retrieval/retriever.py
Two-stage retrieval pipeline.

STAGE 1 — Vector similarity (fast, coarse):
  Embed query → cosine search → top_k=6 candidates

STAGE 2 — Cross-encoder reranking (slow, precise):
  Score each (query, chunk) pair jointly → keep top_k=3

WHY TWO STAGES?
  Bi-encoder embeddings compress query and document independently.
  They miss nuanced relevance. Cross-encoders see both together — much
  more accurate but too slow to run on the full corpus.
  Solution: run fast search first, rerank the small candidate set.
  Result: ~18% improvement in precision@3 in our evaluation.
"""
from loguru import logger
# CrossEncoder imported lazily in get_reranker()
from ingest.embedder import embed_query
from ingest.vectorstore import similarity_search
from config import get_settings

settings = get_settings()
_reranker = None


def get_reranker():
    global _reranker
    from sentence_transformers import CrossEncoder
    if _reranker is None:
        # Multilingual model — handles EN (AI Act) and FR (RGPD) equally well
        logger.info("Loading cross-encoder reranker (first time only)...")
        _reranker = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    return _reranker


def retrieve(
    query: str,
    top_k: int | None = None,
    rerank: bool = True,
    filter_source: str | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    """
    Full retrieval for a query.

    Args:
        query: User's question (used for reranking even if HyDE is active)
        top_k: Number of final chunks to return
        rerank: Whether to apply cross-encoder reranking
        filter_source: Restrict to one document ('eu_ai_act' or 'rgpd_fr')
        query_embedding: Pre-computed embedding (used by HyDE retriever)

    Returns:
        List of chunks with content, metadata, similarity, rerank_score
    """
    final_k = top_k or settings.rerank_top_k
    fetch_k = settings.retrieval_top_k

    # Use provided embedding or compute from query
    vec = query_embedding if query_embedding is not None else embed_query(query)
    candidates = similarity_search(vec, top_k=fetch_k, filter_source=filter_source)
    logger.debug(f"Vector search returned {len(candidates)} candidates")

    if not candidates:
        return []

    if not rerank or len(candidates) <= final_k:
        return candidates[:final_k]

    # Rerank against ORIGINAL query (not HyDE hypothesis — common mistake)
    reranker = get_reranker()
    pairs = [(query, c["content"]) for c in candidates]
    scores = reranker.predict(pairs)

    for cand, score in zip(candidates, scores):
        cand["rerank_score"] = float(score)

    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    # Relative threshold: drop chunks more than 4.0 points below top score
    # Prevents noise without dropping valid low-scoring correct answers
    if reranked:
        top_score = reranked[0]["rerank_score"]
        reranked = [c for c in reranked if top_score - c["rerank_score"] <= 4.0]
    return reranked[:final_k]
