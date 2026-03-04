"""
tests/unit/test_rate_limit.py
Unit tests for rate limiting logic using mock Redis.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


class TestRateLimiting:
    def test_allows_normal_traffic(self):
        """Under the limit — should pass without raising."""
        with patch("middleware.rate_limit.get_redis") as mock_redis, \
             patch("middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_per_minute=20,
                rate_limit_per_day=200
            )
            mock_client = MagicMock()
            mock_client.pipeline.return_value.__enter__ = MagicMock()
            mock_client.pipeline.return_value.execute.return_value = [
                None, None, 5,   # 5 per minute (under 20)
                None, None, None, 50, None  # 50 per day (under 200)
            ]
            mock_redis.return_value = mock_client
            from middleware.rate_limit import check_rate_limit
            check_rate_limit(user_id=1)  # Should not raise

    def test_blocks_on_minute_limit(self):
        """Over per-minute limit — should raise 429."""
        with patch("middleware.rate_limit.get_redis") as mock_redis, \
             patch("middleware.rate_limit.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                rate_limit_per_minute=20,
                rate_limit_per_day=200
            )
            mock_client = MagicMock()
            mock_client.pipeline.return_value.execute.return_value = [
                None, None, 25,  # 25 per minute — OVER 20
                None, None, None, 50, None
            ]
            mock_redis.return_value = mock_client
            from middleware.rate_limit import check_rate_limit
            with pytest.raises(HTTPException) as exc:
                check_rate_limit(user_id=1)
            assert exc.value.status_code == 429

    def test_graceful_degradation_when_redis_down(self):
        """If Redis is unavailable, rate limiting is skipped silently."""
        with patch("middleware.rate_limit.get_redis") as mock_redis:
            mock_redis.return_value = None  # Redis unavailable
            from middleware.rate_limit import check_rate_limit
            check_rate_limit(user_id=1)  # Should NOT raise even without Redis


class TestCaching:
    def test_cache_miss_returns_none(self):
        with patch("cache.redis_cache.get_redis") as mock_redis:
            mock_client = MagicMock()
            mock_client.get.return_value = None
            mock_redis.return_value = mock_client
            from cache.redis_cache import cache_get
            result = cache_get("embed", "test query")
            assert result is None

    def test_cache_hit_returns_value(self):
        import json
        with patch("cache.redis_cache.get_redis") as mock_redis:
            mock_client = MagicMock()
            mock_client.get.return_value = json.dumps([0.1, 0.2, 0.3])
            mock_redis.return_value = mock_client
            from cache.redis_cache import cache_get
            result = cache_get("embed", "test query")
            assert result == [0.1, 0.2, 0.3]

    def test_graceful_degradation_on_error(self):
        with patch("cache.redis_cache.get_redis") as mock_redis:
            mock_client = MagicMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_redis.return_value = mock_client
            from cache.redis_cache import cache_get
            result = cache_get("embed", "test")
            assert result is None  # Returns None, doesn't crash
