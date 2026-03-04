"""
tests/conftest.py
Shared pytest fixtures for all tests.

PATTERN: Use an in-memory SQLite DB for unit tests.
  No Docker required. Tests run in <1 second.
  Integration tests use a real test DB (separate from dev DB).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from auth.models import Base as AuthBase
from db.session import get_db

# ── In-memory test database ──────────────────────────────────────────────────
TEST_DB_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    AuthBase.metadata.create_all(bind=test_engine)
    yield
    AuthBase.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Fresh DB session for each test, rolled back after."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    """FastAPI test client with DB dependency overridden."""
    # Import here to avoid circular imports
    with patch("config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            mistral_api_key="test-key",
            database_url=TEST_DB_URL,
            jwt_secret="test-secret-key-for-testing-only",
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
            rate_limit_per_minute=100,
            rate_limit_per_day=10000,
            cors_origins=["*"],
            debug=True,
        )
        from api.main import app
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


@pytest.fixture
def mock_mistral():
    """Mock Mistral API calls so tests don't cost money."""
    with patch("ingest.embedder.embed_texts") as mock_embed, \
         patch("ingest.embedder.embed_query") as mock_query:
        mock_embed.return_value = [[0.1] * 1024]
        mock_query.return_value = [0.1] * 1024
        yield {"embed_texts": mock_embed, "embed_query": mock_query}


@pytest.fixture
def test_user_token(client):
    """Register a test user and return their JWT token."""
    resp = client.post("/auth/register", json={
        "email": "test@clausio.ai",
        "password": "testpassword123"
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(test_user_token):
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {test_user_token}"}
