# pyre-ignore-all-errors
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from config import get_settings
from auth.models import UserDB
from auth.dependencies import get_current_user
from services.ingest_service import process_ingestion
from middleware.rate_limit import check_rate_limit

settings = get_settings()
router = APIRouter(prefix="/ingest", tags=["Ingest"])

@router.post("")
async def ingest_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: UserDB = Depends(get_current_user),
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
        
    check_rate_limit(current_user.id, "ingest")
    
    if not current_user.is_admin and settings.environment == "production":
        raise HTTPException(status_code=403, detail="Admin access required for ingestion")
        
    # File I/O happens in router so we can safely pass bytes directly to the agnostic service
    content = await file.read()
    
    background_tasks.add_task(process_ingestion, content, file.filename, current_user.id)
    return {"message": f"Ingestion started for '{file.filename}'"}
