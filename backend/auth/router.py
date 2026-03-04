"""
auth/router.py
Authentication endpoints: register, login, profile, API key management.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from auth.models import (
    UserDB, UserCreate, UserLogin, UserResponse, Token,
    hash_password, verify_password, create_access_token, generate_api_key
)
from auth.dependencies import get_current_user
from db.session import get_db
from config import get_settings

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.
    Returns a JWT access token immediately — no email verification for simplicity.
    Production: add email verification before activating account.
    """
    existing = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = UserDB(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        {"sub": user.email, "user_id": user.id},
        timedelta(minutes=settings.jwt_expire_minutes)
    )
    logger.info(f"New user registered: {user.email}")
    return Token(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and return JWT token."""
    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        # Same error message for both cases — prevents user enumeration attacks
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token(
        {"sub": user.email, "user_id": user.id},
        timedelta(minutes=settings.jwt_expire_minutes)
    )
    logger.info(f"User logged in: {user.email}")
    return Token(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: UserDB = Depends(get_current_user)):
    """Get current user profile."""
    return current_user


@router.post("/api-key")
async def create_api_key(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a permanent API key for programmatic access.
    Use this for CLI tools, scripts, and integrations.
    Format: csk-xxxxx (same pattern as OpenAI's sk-xxxx)
    """
    key = generate_api_key()
    current_user.api_key = key
    db.commit()
    return {
        "api_key": key,
        "note": "Store this securely — it won't be shown again.",
        "usage": "Add header: X-API-Key: " + key
    }


@router.delete("/api-key")
async def revoke_api_key(
    current_user: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke current API key."""
    current_user.api_key = None
    db.commit()
    return {"message": "API key revoked"}
