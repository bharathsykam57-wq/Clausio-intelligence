from fastapi import APIRouter, Depends
from db.session import check_db_health
from ingest.vectorstore import get_document_count
from cache.redis_cache import get_redis
from config import get_settings
from auth.models import UserDB
from auth.dependencies import get_current_user
from middleware.rate_limit import get_rate_limit_status

settings = get_settings()
router = APIRouter(tags=["System"])

@router.get("/health")
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

@router.get("/rate-limit/status")
async def rate_limit_status(current_user: UserDB = Depends(get_current_user)):
    return get_rate_limit_status(current_user.id)

@router.get("/stats")
async def stats(current_user: UserDB = Depends(get_current_user)):
    return {
        "documents_indexed": get_document_count(),
        "features": ["hyde", "query_routing", "contradiction", "confidence", "followups",
                     "jwt_auth", "api_key_auth", "rate_limiting", "redis_caching", "audit_log"],
    }
