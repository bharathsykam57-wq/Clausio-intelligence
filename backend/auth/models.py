"""
auth/models.py
User model and JWT token logic.

WHY JWT?
  Stateless — no session store needed. Every request carries a signed token.
  The server verifies the signature without hitting the database.
  Standard for REST APIs. Used by Stripe, GitHub, every real SaaS.

TOKEN FLOW:
  1. POST /auth/register → create user, return access_token
  2. POST /auth/login    → verify password, return access_token
  3. GET  /chat          → Bearer token in header → verified → allowed
"""

# Standard Library
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, Boolean, DateTime, Integer, text
from sqlalchemy.orm import declarative_base
from config import get_settings

settings = get_settings()
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── SQLAlchemy User Model ────────────────────────────────────────────────────

class UserDB(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active     = Column(Boolean, default=True)
    is_admin      = Column(Boolean, default=False)
    api_key       = Column(String, unique=True, index=True, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    # Rate limit tracking
    requests_today = Column(Integer, default=0)
    last_request_date = Column(String, nullable=True)

# ── Pydantic Schemas ─────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int   # seconds

class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[int] = None

# ── Password Utilities ───────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ── JWT Utilities ────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if email is None:
            raise JWTError("No subject in token")
        return TokenData(email=email, user_id=user_id)
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")

import secrets

def generate_api_key() -> str:
    """Generate a secure random API key for programmatic access."""
    return f"csk-{secrets.token_urlsafe(32)}"
