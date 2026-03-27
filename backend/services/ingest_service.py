# pyre-ignore-all-errors
from loguru import logger
from ingest.loader import load_pdf_from_bytes, chunk_documents
from ingest.embedder import embed_documents_batched
from ingest.vectorstore import insert_documents
from cache.redis_cache import invalidate_responses

def process_ingestion(content: bytes, filename: str, user_id: int) -> int:
    """
    Core business logic for parsing, embedding, and storing PDF byte streams.
    Framework-agnostic processor suitable for background execution or CLI use.
    Throws ValueError on ingestion or parsing failure.
    """
    try:
        title = filename.replace(".pdf", "")
        pages = load_pdf_from_bytes(content, {"source": "upload", "title": title})
        chunks = chunk_documents(pages)
        embedded = embed_documents_batched(chunks)
        count = insert_documents(embedded)
        
        # Wipe domain cache state upon successful vector manipulation
        invalidate_responses()
        
        logger.info(f"User {user_id} ingested '{filename}': {count} chunks")
        return count
    except Exception as e:
        logger.error(f"Ingestion pipeline failed for '{filename}' by user {user_id}: {e}")
        raise ValueError("Failed to ingest document content") from e
