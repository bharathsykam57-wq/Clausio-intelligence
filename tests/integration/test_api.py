"""
tests/integration/test_api.py
Integration tests — test the full API through HTTP.

These tests use the TestClient which runs the full FastAPI app
with a test database. No real Mistral calls are made (mocked).
"""
import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestAuthentication:
    def test_register_new_user(self, client):
        resp = client.post("/auth/register", json={
            "email": "newuser@test.com",
            "password": "password123"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client):
        client.post("/auth/register", json={"email": "dup@test.com", "password": "pass1234"})
        resp = client.post("/auth/register", json={"email": "dup@test.com", "password": "pass1234"})
        assert resp.status_code == 400

    def test_login_valid_credentials(self, client):
        client.post("/auth/register", json={"email": "login@test.com", "password": "pass1234"})
        resp = client.post("/auth/login", json={"email": "login@test.com", "password": "pass1234"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        client.post("/auth/register", json={"email": "wp@test.com", "password": "correct"})
        resp = client.post("/auth/login", json={"email": "wp@test.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_get_profile_authenticated(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@clausio.ai"

    def test_get_profile_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_api_key_creation(self, client, auth_headers):
        resp = client.post("/auth/api-key", headers=auth_headers)
        assert resp.status_code == 200
        key = resp.json()["api_key"]
        assert key.startswith("csk-")

    def test_auth_with_api_key(self, client, auth_headers):
        # Create API key
        resp = client.post("/auth/api-key", headers=auth_headers)
        api_key = resp.json()["api_key"]
        # Use API key to access protected endpoint
        resp2 = client.get("/auth/me", headers={"X-API-Key": api_key})
        assert resp2.status_code == 200


class TestChatEndpoint:
    def test_chat_requires_auth(self, client):
        resp = client.post("/chat", json={"question": "What is the EU AI Act?"})
        assert resp.status_code == 401

    def test_chat_with_valid_auth(self, client, auth_headers):
        mock_result = {
            "answer": "The EU AI Act is a regulation...",
            "sources": [],
            "chunks_used": 3,
            "query_type": "SINGLE_CHUNK",
            "confidence": {"level": "HIGH", "score": 0.9, "message": "Strong match"},
            "contradiction": {"has_contradiction": False, "explanation": "", "checked": False},
            "follow_up_questions": ["What are the penalties?"],
        }
        with patch("api.main.answer", return_value=mock_result):
            resp = client.post("/chat", json={"question": "What is the EU AI Act?"}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "confidence" in data
        assert "follow_up_questions" in data

    def test_chat_empty_question_rejected(self, client, auth_headers):
        resp = client.post("/chat", json={"question": ""}, headers=auth_headers)
        assert resp.status_code == 400

    def test_chat_response_has_all_fields(self, client, auth_headers):
        mock_result = {
            "answer": "Test answer",
            "sources": [{"title": "EU AI Act", "page": 5, "source_key": "eu_ai_act", "url": None, "similarity": 0.9}],
            "chunks_used": 2,
            "query_type": "SINGLE_CHUNK",
            "confidence": {"level": "HIGH", "score": 0.85, "message": "Strong match"},
            "contradiction": {"has_contradiction": False, "explanation": "", "checked": True},
            "follow_up_questions": ["What are prohibited AI systems?"],
        }
        with patch("api.main.answer", return_value=mock_result):
            resp = client.post("/chat", json={"question": "Test?"}, headers=auth_headers)
        data = resp.json()
        # Verify all v2 fields present
        required_fields = ["answer", "sources", "query_type", "confidence", "contradiction", "follow_up_questions"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestRateLimitHeaders:
    def test_rate_limit_status_endpoint(self, client, auth_headers):
        resp = client.get("/rate-limit/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "limit_per_minute" in data
        assert "limit_per_day" in data
