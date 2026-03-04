"""
cache/redis_cache.py
Redis caching for embeddings and query results.

WHY CACHE?
  Same question asked 100 times = 100 Mistral API calls = $0.10 wasted.
  With cache: 1 API call + 99 cache hits = $0.001.

  More importantly: cached responses are <5ms vs 2000ms uncached.
  Real users notice this. It's the difference between "fast" and "usable."

WHAT WE CACHE:
  1. Query embeddings     — TTL: 24h  (same query → same vector)
  2. Full RAG responses   — TTL: 1h   (answers can change if docs updated)
  3. Query classifications — TTL: 6h  (same question type doesn't change)

GRACEFUL DEGRADATION:
  If Redis is down, we fall back to no caching.
  The app still works — just slower and costs more.
  Never let a cache failure bring down the core product.
"""
import json
import hashlib
from typing import Any, Optional
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import get_settings

settings = get_settings()
_client: Any = None


def get_redis():
    global _client
    if not REDIS_AVAILABLE:
        return None
    if _client is None:
        try:
            _client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis unavailable — running without cache: {e}")
            _client = None
    return _client


def _make_key(prefix: str, value: str) -> str:
    """Create a namespaced cache key from a hash of the value."""
    hashed = hashlib.sha256(value.encode()).hexdigest()[:16]
    return f"clausio:{prefix}:{hashed}"


def cache_get(prefix: str, key: str) -> Optional[Any]:
    """Retrieve from cache. Returns None on miss or error."""
    client = get_redis()
    if not client:
        return None
    try:
        raw = client.get(_make_key(prefix, key))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Cache get failed: {e}")
    return None


def cache_set(prefix: str, key: str, value: Any, ttl: int = 3600) -> bool:
    """Store in cache. Returns False on error."""
    client = get_redis()
    if not client:
        return False
    try:
        client.setex(_make_key(prefix, key), ttl, json.dumps(value))
        return True
    except Exception as e:
        logger.warning(f"Cache set failed: {e}")
        return False


def cache_delete(prefix: str, key: str) -> bool:
    client = get_redis()
    if not client:
        return False
    try:
        client.delete(_make_key(prefix, key))
        return True
    except Exception as e:
        logger.warning(f"Cache delete failed: {e}")
        return False


# ── Specific cache helpers ───────────────────────────────────────────────────

def get_cached_embedding(text: str) -> Optional[list[float]]:
    return cache_get("embed", text)

def set_cached_embedding(text: str, vector: list[float]) -> None:
    cache_set("embed", text, vector, ttl=86400)  # 24 hours

def get_cached_response(question: str) -> Optional[dict]:
    return cache_get("response", question)

def set_cached_response(question: str, response: dict) -> None:
    cache_set("response", question, response, ttl=3600)  # 1 hour

def get_cached_query_type(question: str) -> Optional[str]:
    return cache_get("qtype", question)

def set_cached_query_type(question: str, query_type: str) -> None:
    cache_set("qtype", question, query_type, ttl=21600)  # 6 hours

def invalidate_responses() -> None:
    """Call after re-ingestion to clear stale cached answers."""
    client = get_redis()
    if not client:
        return
    try:
        keys = client.keys("clausio:response:*")
        if keys:
            client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cached responses")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")
