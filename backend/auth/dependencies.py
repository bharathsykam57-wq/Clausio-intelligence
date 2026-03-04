"""
auth/dependencies.py
FastAPI dependency injection for authentication.

USAGE in routes:
  @app.post("/chat")
  async def chat(request: ChatRequest, user: UserDB = Depends(get_current_user)):
      # user is guaranteed to be authenticated here

TWO AUTH METHODS supported:
  1. Bearer JWT token  →  Authorization: Bearer <token>
  2. API key           →  X-API-Key: csk-xxxxx
     (for programmatic / CLI access — same as OpenAI's pattern)
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from loguru import logger

from auth.models import UserDB, decode_token
from db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> UserDB:
    """
    Authenticate via JWT Bearer token OR API key.
    Raises 401 if neither is provided or both are invalid.
    """
    # Try API key first (faster — no JWT decode needed)
    if api_key:
        user = db.query(UserDB).filter(UserDB.api_key == api_key, UserDB.is_active == True).first()
        if user:
            return user

    # Try JWT Bearer token
    if credentials:
        try:
            token_data = decode_token(credentials.credentials)
            user = db.query(UserDB).filter(
                UserDB.email == token_data.email,
                UserDB.is_active == True
            ).first()
            if user:
                return user
        except ValueError as e:
            logger.warning(f"Invalid token: {e}")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_admin_user(user: UserDB = Depends(get_current_user)) -> UserDB:
    """Require admin role."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> UserDB | None:
    """Return user if authenticated, None if not. For public endpoints with optional auth."""
    try:
        return await get_current_user(credentials, api_key, db)
    except HTTPException:
        return None
