"""
middleware/rate_limit.py
Per-user rate limiting using Redis sliding window.

WHY RATE LIMIT?
  Without it: one user can send 10,000 requests and drain your Mistral credits.
  With it: each user gets a fair quota. Abuse is blocked automatically.

TWO LIMITS:
  1. Per-minute limit  → prevents burst abuse (default: 20 req/min)
  2. Per-day limit     → controls total cost (default: 200 req/day)

SLIDING WINDOW algorithm:
  More accurate than fixed window (no "reset at midnight" gaming).
  Uses Redis sorted sets — each request is scored by timestamp.
  Count requests in [now - window_size, now] to get current rate.

GRACEFUL DEGRADATION:
  If Redis is down, rate limiting is skipped (app works normally).
  Never let rate limiter break core functionality.
"""
from datetime import datetime
from fastapi import HTTPException, Request, status
from loguru import logger
from cache.redis_cache import get_redis
from config import get_settings

settings = get_settings()

# Rate limit settings (can be overridden by environment variables)
def check_rate_limit(user_id: int, endpoint: str = "chat") -> None:
    """
    Check if user has exceeded rate limits.
    Raises HTTP 429 if limit exceeded.

    Args:
        user_id: The authenticated user's ID
        endpoint: Which endpoint (different limits per endpoint)
    """
    client = get_redis()
    if not client:
        return  # Graceful degradation — skip if Redis is down

    now = datetime.utcnow().timestamp()
    key_minute = f"clausio:rl:{user_id}:{endpoint}:minute"
    key_day    = f"clausio:rl:{user_id}:{endpoint}:day"

    try:
        pipe = client.pipeline()

        # Sliding window: remove entries older than 1 minute
        pipe.zremrangebyscore(key_minute, 0, now - 60)
        pipe.zadd(key_minute, {str(now): now})
        pipe.zcard(key_minute)
        pipe.expire(key_minute, 120)

        # Sliding window: remove entries older than 24 hours
        pipe.zremrangebyscore(key_day, 0, now - 86400)
        pipe.zadd(key_day, {str(now) + "_d": now})
        pipe.zcard(key_day)
        pipe.expire(key_day, 90000)

        results = pipe.execute()
        count_minute = results[2]
        count_day    = results[6]

        if count_minute > settings.rate_limit_per_minute:
            logger.warning(f"User {user_id} hit per-minute rate limit")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Limit: {settings.rate_limit_per_minute}/minute.",
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        if count_day > settings.rate_limit_per_day:
            logger.warning(f"User {user_id} hit daily rate limit")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "daily_limit_exceeded",
                    "message": f"Daily limit reached. Limit: {settings.rate_limit_per_day}/day.",
                    "retry_after_seconds": 86400,
                },
                headers={"Retry-After": "86400"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Rate limit check error (skipping): {e}")


def get_rate_limit_status(user_id: int, endpoint: str = "chat") -> dict:
    """Return current usage stats for a user."""
    client = get_redis()
    if not client:
        return {"available": True, "redis": "unavailable"}

    now = datetime.utcnow().timestamp()
    key_minute = f"clausio:rl:{user_id}:{endpoint}:minute"
    key_day    = f"clausio:rl:{user_id}:{endpoint}:day"

    try:
        count_minute = client.zcount(key_minute, now - 60, now)
        count_day    = client.zcount(key_day, now - 86400, now)
        return {
            "requests_this_minute": count_minute,
            "requests_today": count_day,
            "limit_per_minute": settings.rate_limit_per_minute,
            "limit_per_day": settings.rate_limit_per_day,
            "remaining_today": max(0, settings.rate_limit_per_day - count_day),
        }
    except Exception:
        return {"available": True, "redis": "error"}
