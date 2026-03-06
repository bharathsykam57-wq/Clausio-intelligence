"""
api/main.py — Production-grade FastAPI with auth, rate limiting, caching, audit logging.
"""

# Standard Library 
import time, json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from config import get_settings
from chain.rag_chain import answer, answer_stream
from ingest.vectorstore import get_document_count
from ingest.loader import load_pdf_from_bytes, chunk_documents
from ingest.embedder import embed_documents_batched
from ingest.vectorstore import insert_documents
from db.session import get_db, check_db_health
from db.init import init_all_tables
from auth.models import UserDB
from auth.router import router as auth_router
from auth.dependencies import get_current_user
from middleware.rate_limit import check_rate_limit, get_rate_limit_status
from middleware.logging import RequestLoggingMiddleware
from middleware.errors import register_error_handlers
from cache.redis_cache import get_cached_response, set_cached_response, invalidate_responses, get_redis

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.version} [{settings.environment}]")
    init_all_tables()
    count = get_document_count()
    redis_ok = get_redis() is not None
    logger.info(f"Ready — {count} docs | Redis: {'OK' if redis_ok else 'UNAVAILABLE (degraded)'}")
    yield

app = FastAPI(title="Clausio API", version=settings.version, lifespan=lifespan,
              docs_url="/docs" if settings.environment != "production" else None)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
register_error_handlers(app)
app.include_router(auth_router)

# ── Schemas ──────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = []
    filter_source: str | None = None
    use_cache: bool = True

class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    chunks_used: int
    query_type: str
    confidence: dict
    contradiction: dict
    follow_up_questions: list[str]
    cached: bool = False

# ── Audit log ────────────────────────────────────────────────────────────────

def log_request(db, user_id, question, result, latency_ms):
    try:
        from sqlalchemy import text
        db.execute(text("""
            INSERT INTO request_logs (user_id, question, query_type, latency_ms, chunks_used, confidence, created_at)
            VALUES (:uid, :q, :qt, :lat, :cu, :conf, NOW())
        """), {"uid": user_id, "q": question[:500], "qt": result.get("query_type",""),
               "lat": latency_ms, "cu": result.get("chunks_used",0),
               "conf": result.get("confidence",{}).get("level","")})
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log failed: {e}")

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    db_status = check_db_health()
    return {
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "version": settings.version,
        "environment": settings.environment,
        "documents_indexed": get_document_count(),
        "services": {
            "database": db_status,
            "redis": {"status": "ok" if get_redis() else "unavailable"},
        },
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    check_rate_limit(current_user.id)

    # Cache check (single-turn only)
    if request.use_cache and not request.history:
        cached = get_cached_response(request.question.strip().lower())
        if cached:
            return {**cached, "cached": True}

    history = [{"role": m.role, "content": m.content} for m in request.history]
    start = time.perf_counter()
    try:
        result = answer(request.question, history, request.filter_source)
    except Exception as e:
        logger.error(f"RAG error user={current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate answer")

    latency_ms = int((time.perf_counter() - start) * 1000)
    result["cached"] = False
    if request.use_cache and not request.history:
        set_cached_response(request.question.strip().lower(), result)
    background_tasks.add_task(log_request, db, current_user.id, request.question, result, latency_ms)
    return result

@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: UserDB = Depends(get_current_user),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    check_rate_limit(current_user.id)
    history = [{"role": m.role, "content": m.content} for m in request.history]

    async def event_generator():
        try:
            async for token in answer_stream(request.question, history, request.filter_source):
                if token.startswith("[[METADATA]]"):
                    yield f"event: metadata\ndata: {token[len('[[METADATA]]'):]}\n\n"
                else:
                    yield f"data: {token.replace(chr(10), chr(92)+'n')}\n\n"
        except Exception as e:
            logger.error(f"Stream error user={current_user.id}: {e}")
            yield f"event: error\ndata: {json.dumps({'error': 'Stream failed'})}\n\n"
        finally:
            yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.post("/ingest")
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: UserDB = Depends(get_current_user),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
    if not current_user.is_admin and settings.environment == "production":
        raise HTTPException(status_code=403, detail="Admin access required for ingestion")
    content = await file.read()
    def ingest_task():
        pages = load_pdf_from_bytes(content, {"source": "upload", "title": file.filename.replace(".pdf","")})
        chunks = chunk_documents(pages)
        embedded = embed_documents_batched(chunks)
        count = insert_documents(embedded)
        invalidate_responses()
        logger.info(f"User {current_user.id} ingested '{file.filename}': {count} chunks")
    background_tasks.add_task(ingest_task)
    return {"message": f"Ingestion started for '{file.filename}'"}

@app.get("/rate-limit/status")
async def rate_limit_status(current_user: UserDB = Depends(get_current_user)):
    return get_rate_limit_status(current_user.id)

@app.get("/stats")
async def stats(current_user: UserDB = Depends(get_current_user)):
    return {
        "documents_indexed": get_document_count(),
        "features": ["hyde", "query_routing", "contradiction", "confidence", "followups",
                     "jwt_auth", "api_key_auth", "rate_limiting", "redis_caching", "audit_log"],
    }
