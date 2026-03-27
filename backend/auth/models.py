# pyre-ignore-all-errors
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
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, String, Boolean, DateTime, Integer, text
from sqlalchemy.orm import declarative_base
from config import get_settings

settings = get_settings()
Base = declarative_base()

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
