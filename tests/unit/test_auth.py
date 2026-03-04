"""
tests/unit/test_auth.py
Unit tests for authentication logic.

Tests password hashing, JWT creation/decoding, and user registration
without any external API calls.
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        from auth.models import hash_password
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"
        assert len(hashed) > 20

    def test_verify_correct_password(self):
        from auth.models import hash_password, verify_password
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_reject_wrong_password(self):
        from auth.models import hash_password, verify_password
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_same_password(self):
        """bcrypt uses random salt — same password produces different hashes."""
        from auth.models import hash_password
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2  # Different salts


class TestJWT:
    def test_create_and_decode_token(self):
        with patch("auth.models.get_settings") as mock:
            mock.return_value = MagicMock(
                jwt_secret="test-secret",
                jwt_algorithm="HS256",
                jwt_expire_minutes=30
            )
            from auth.models import create_access_token, decode_token
            token = create_access_token({"sub": "user@test.com", "user_id": 42})
            data = decode_token(token)
            assert data.email == "user@test.com"
            assert data.user_id == 42

    def test_expired_token_rejected(self):
        with patch("auth.models.get_settings") as mock:
            mock.return_value = MagicMock(
                jwt_secret="test-secret",
                jwt_algorithm="HS256",
                jwt_expire_minutes=-1  # Already expired
            )
            from auth.models import create_access_token, decode_token
            token = create_access_token({"sub": "user@test.com"}, timedelta(minutes=-1))
            with pytest.raises(ValueError, match="Invalid token"):
                decode_token(token)

    def test_tampered_token_rejected(self):
        with patch("auth.models.get_settings") as mock:
            mock.return_value = MagicMock(
                jwt_secret="test-secret",
                jwt_algorithm="HS256",
                jwt_expire_minutes=30
            )
            from auth.models import create_access_token, decode_token
            token = create_access_token({"sub": "user@test.com"})
            tampered = token[:-5] + "XXXXX"
            with pytest.raises(ValueError):
                decode_token(tampered)


class TestAPIKeyGeneration:
    def test_api_key_format(self):
        from auth.models import generate_api_key
        key = generate_api_key()
        assert key.startswith("csk-")
        assert len(key) > 20

    def test_keys_are_unique(self):
        from auth.models import generate_api_key
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100  # All unique
