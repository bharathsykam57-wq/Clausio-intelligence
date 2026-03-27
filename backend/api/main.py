# pyre-ignore-all-errors
"""
api/main.py — Production-grade FastAPI with auth, rate limiting, caching, audit logging.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config import get_settings
from ingest.vectorstore import get_document_count
from db.init import init_all_tables
from middleware.logging import RequestLoggingMiddleware
from middleware.errors import register_error_handlers
from cache.redis_cache import get_redis

from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.ingest import router as ingest_router
from api.routes.system import router as system_router

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.version} [{settings.environment}]")
    init_all_tables()
    count = get_document_count()
    redis_ok = get_redis() is not None
    logger.info(f"Ready — {count} docs | Redis: {'OK' if redis_ok else 'UNAVAILABLE (degraded)'}")
    yield

app = FastAPI(
    title="Clausio API", 
    version=settings.version, 
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=settings.cors_origins,
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)
register_error_handlers(app)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(ingest_router)
app.include_router(system_router)
