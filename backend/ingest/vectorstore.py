"""
ingest/vectorstore.py
Manages pgvector database: table creation, insertion, similarity search.

WHY pgvector over Pinecone/Qdrant?
  - No external SaaS dependency — data stays in your PostgreSQL
  - GDPR-compliant: no data leaves your infrastructure
  - IVFFlat index: sub-10ms search up to ~500k vectors
  - One less service to manage in production
"""
import json
from typing import Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from loguru import logger
from config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """
    Create pgvector extension + documents table + IVFFlat index.
    Safe to call multiple times (uses IF NOT EXISTS).
    1024 dimensions matches mistral-embed output exactly.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                id         BIGSERIAL PRIMARY KEY,
                content    TEXT NOT NULL,
                embedding  vector(1024) NOT NULL,
                metadata   JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        # IVFFlat index: lists=100 is optimal for up to ~1M rows
        # Uses cosine distance (best for normalized embedding vectors)
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.commit()
    logger.info("Database initialized")


def insert_documents(embedded_docs: list[dict[str, Any]]) -> int:
    """Insert embedded documents. Returns count inserted."""
    with engine.connect() as conn:
        count = 0
        for doc in embedded_docs:
            conn.execute(
                text("INSERT INTO documents (content, embedding, metadata) VALUES (:content, :embedding, :metadata)"),
                {"content": doc["content"], "embedding": str(doc["embedding"]), "metadata": json.dumps(doc["metadata"])},
            )
            count += 1
        conn.commit()
    logger.info(f"Inserted {count} documents")
    return count


def similarity_search(query_embedding: list[float], top_k: int = 6, filter_source: str | None = None) -> list[dict]:
    """
    Cosine similarity search.
    Returns top_k chunks with content, metadata, and similarity score.
    Optionally filter by source document key.
    """
    with engine.connect() as conn:
        if filter_source:
            result = conn.execute(
                text("""
                    SELECT content, metadata, 1 - (embedding <=> :emb::vector) AS similarity
                    FROM documents WHERE metadata->>'source' = :src
                    ORDER BY embedding <=> :emb::vector LIMIT :k
                """),
                {"emb": str(query_embedding), "src": filter_source, "k": top_k},
            )
        else:
            result = conn.execute(
                text("""
                    SELECT content, metadata, 1 - (embedding <=> :emb::vector) AS similarity
                    FROM documents
                    ORDER BY embedding <=> :emb::vector LIMIT :k
                """),
                {"emb": str(query_embedding), "k": top_k},
            )
        rows = result.fetchall()
    return [
        {
            "content": row.content,
            "metadata": row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata),
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


def get_document_count() -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()


def clear_documents() -> None:
    """Delete all documents. Use when re-ingesting from scratch."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM documents"))
        conn.commit()
    logger.warning("All documents cleared from database")
