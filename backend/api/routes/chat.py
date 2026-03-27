# pyre-ignore-all-errors
import time
import json
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from config import get_settings
from chain.rag_chain import answer_stream
from db.session import get_db
from auth.models import UserDB
from auth.dependencies import get_current_user
from middleware.rate_limit import check_rate_limit
from services.rag_service import process_chat, log_audit_request

settings = get_settings()
router = APIRouter(prefix="/chat", tags=["Chat"])

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

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    check_rate_limit(current_user.id)

    history = [{"role": m.role, "content": m.content} for m in request.history]
    
    try:
        result, latency_ms, is_cached = process_chat(
            request.question, history, request.filter_source, request.use_cache
        )
    except ValueError as e:
        logger.error(f"process_chat user={current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not is_cached:
        background_tasks.add_task(log_audit_request, db, current_user.id, request.question, result, latency_ms)

    return result

@router.post("/stream")
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
