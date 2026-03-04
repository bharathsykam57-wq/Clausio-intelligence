from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────
    app_name: str = "Clausio"
    version: str = "2.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False

    # ── Mistral AI ───────────────────────────────────────────────────────
    mistral_api_key: str
    mistral_embed_model: str = "mistral-embed"
    mistral_chat_model: str = "mistral-large-latest"

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "postgresql://lexia:lexia@localhost:5432/lexia"

    # ── Redis ────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── Auth / JWT ───────────────────────────────────────────────────────
    jwt_secret: str = "change-this-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── Rate Limiting ────────────────────────────────────────────────────
    rate_limit_per_minute: int = 20
    rate_limit_per_day: int = 200

    # ── RAG Parameters ───────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64
    retrieval_top_k: int = 6
    rerank_top_k: int = 3

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
