"""
ingest/embedder.py
Wraps Mistral embedding API with batching and retry logic.

WHY mistral-embed?
  - 1024 dimensions (good balance of precision vs storage)
  - Natively multilingual (handles both EN AI Act and FR RGPD)
  - EU data residency — critical for French enterprise clients
  - Coherent stack: same provider for embed + chat
"""
import time
from typing import Any
from langchain.schema import Document
from langchain_mistralai import MistralAIEmbeddings
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from config import get_settings

settings = get_settings()
_embeddings: MistralAIEmbeddings | None = None


def get_embeddings() -> MistralAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = MistralAIEmbeddings(
            model=settings.mistral_embed_model,
            mistral_api_key=settings.mistral_api_key,
        )
    return _embeddings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Retries up to 3x on rate limit errors."""
    return get_embeddings().embed_documents(texts)


def embed_query(query: str) -> list[float]:
    """Embed a single query string for similarity search."""
    return get_embeddings().embed_query(query)


def embed_documents_batched(docs: list[Document], batch_size: int = 32) -> list[dict[str, Any]]:
    """
    Embed all documents in batches.
    batch_size=32 stays well within Mistral's rate limits.
    Sleep 0.5s between batches to avoid 429 errors on free tier.
    """
    results = []
    total = len(docs)
    for i in range(0, total, batch_size):
        batch = docs[i: i + batch_size]
        texts = [doc.page_content for doc in batch]
        logger.info(f"Embedding batch {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}")
        vectors = embed_texts(texts)
        for doc, vector in zip(batch, vectors):
            results.append({"content": doc.page_content, "embedding": vector, "metadata": doc.metadata})
        if i + batch_size < total:
            time.sleep(0.5)
    logger.info(f"Embedded {len(results)} documents")
    return results
