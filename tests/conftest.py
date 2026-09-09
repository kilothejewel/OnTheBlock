"""
Shared test fixtures.

The suite runs entirely against an in-memory SQLite database (no Postgres, no
network). A single shared connection is kept alive with SQLAlchemy's StaticPool so
every session in a test sees the same data. External services (OpenAI, Google
Places) are monkeypatched in the tests that need them.
"""

import os

# Provide the settings the app requires *before* importing it, so the suite runs
# without a .env file (e.g. in CI). os.environ wins over any .env that is present.
os.environ.setdefault("OTB_POSTGRES_SERVER", "localhost")
os.environ.setdefault("OTB_POSTGRES_USER", "test")
os.environ.setdefault("OTB_POSTGRES_PASSWORD", "test")
os.environ.setdefault("OTB_POSTGRES_DB", "test")
os.environ.setdefault("OTB_SUPABASE_URL", "http://localhost")
os.environ.setdefault("OTB_SUPABASE_KEY", "test")
os.environ.setdefault("OTB_OPENAI_API_KEY", "your_openai_api_key")
os.environ.setdefault("OTB_GOOGLE_PLACES_API_KEY", "your_google_places_api_key")
os.environ.setdefault("OTB_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OTB_DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.main import app

# Rate limiting is exercised by hand in Phase 2's verification; here it would just
# cause flaky 429s once the whole suite exceeds the global default, so disable it.
limiter.enabled = False

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _create_schema():
    """Fresh tables for every test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """A TestClient whose get_db dependency points at the in-memory test database."""

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Register a user and return an Authorization header for them."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "tester@example.com",
            "username": "tester",
            "password": "supersecret123",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
