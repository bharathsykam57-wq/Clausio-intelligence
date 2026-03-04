"""
db/session.py
SQLAlchemy session factory with production connection pooling.

WHY CONNECTION POOLING MATTERS:
  Without pooling: each request opens a new DB connection → 500ms overhead,
  connection limit hit under any real load.

  With pooling: connections are reused from a pool → <1ms overhead,
  handles 100+ concurrent requests.

POOL SETTINGS EXPLAINED:
  pool_size=10        → 10 persistent connections always open
  max_overflow=20     → allow 20 extra connections under burst load
  pool_timeout=30     → wait 30s for a connection before raising error
  pool_recycle=3600   → recycle connections every hour (prevents stale connections)
  pool_pre_ping=True  → test connection before use (handles DB restarts)
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from loguru import logger
from config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=settings.debug,  # Log SQL queries only in debug mode
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    FastAPI dependency that provides a database session.
    Automatically closes the session when the request completes.

    Usage:
        @app.get("/endpoint")
        async def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health() -> dict:
    """Check database connectivity. Used in /health endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok", "pool_size": engine.pool.size(), "checked_out": engine.pool.checkedout()}
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        return {"status": "error", "detail": str(e)}
