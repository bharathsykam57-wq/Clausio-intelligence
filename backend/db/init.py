"""
db/init.py
Creates all database tables on startup.
Safe to run multiple times (CREATE IF NOT EXISTS).
"""
from sqlalchemy import text
from loguru import logger
from db.session import engine
from auth.models import Base as AuthBase


def init_all_tables() -> None:
    # Create documents table with vector extension for embeddings
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
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.commit()

    # users table created here first
    AuthBase.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS request_logs (
                id          BIGSERIAL PRIMARY KEY,
                user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                question    TEXT,
                query_type  VARCHAR(20),
                latency_ms  INTEGER,
                chunks_used INTEGER,
                confidence  VARCHAR(10),
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.commit()

    logger.info("All database tables initialized")