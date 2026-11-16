"""
Shared test fixtures.

The suite runs against an in-memory SQLite database by default (no network). A
single shared connection is kept alive with SQLAlchemy's StaticPool so every
session in a test sees the same data. Set OTB_TEST_DATABASE_URL to run the same
tests against Postgres, as CI does. The app's shared HTTP client is replaced
for every test (outbound_http), so Google is answered by the test or not at
all; OpenAI is monkeypatched in the tests that need it.
"""

import os

# Provide the settings the app requires *before* importing it, so the suite runs
# without a .env file (e.g. in CI). os.environ wins over any .env that is present.
os.environ.setdefault("OTB_POSTGRES_SERVER", "localhost")
os.environ.setdefault("OTB_POSTGRES_USER", "test")
os.environ.setdefault("OTB_POSTGRES_PASSWORD", "test")
os.environ.setdefault("OTB_POSTGRES_DB", "test")
os.environ.setdefault("OTB_OPENAI_API_KEY", "your_openai_api_key")
os.environ.setdefault("OTB_GOOGLE_PLACES_API_KEY", "your_google_places_api_key")
os.environ.setdefault("OTB_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OTB_DATABASE_URL", "sqlite://")
os.environ.setdefault("OTB_FRONTEND_ORIGIN_REGEX", r"^http://(localhost|127\.0\.0\.1|\[::1\]):\d+$")

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import http_client
from app.core.config import with_postgres_driver
from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.main import app

# Rate limiting is exercised by hand in Phase 2's verification; here it would just
# cause flaky 429s once the whole suite exceeds the global default, so disable it.
limiter.enabled = False

# Tests run on in-memory SQLite by default. CI also runs them against real
# Postgres (production's database) by setting OTB_TEST_DATABASE_URL.
TEST_DATABASE_URL = with_postgres_driver(os.environ.get("OTB_TEST_DATABASE_URL", "sqlite://"))
if TEST_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _create_schema():
    """Fresh tables for every test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class OutboundHttp:
    """Stands in for the network: records the app's outbound requests and answers them."""

    def __init__(self):
        self.requests = []
        self._handler = None

    def respond_with(self, handler):
        """Answer every request with handler(request): an httpx.Response, or raise an httpx error."""
        self._handler = handler

    def handle(self, request):
        self.requests.append(request)
        if self._handler is None:
            raise AssertionError(f"A test made an outbound request it did not expect: {request.method} {request.url}")
        return self._handler(request)


@pytest.fixture(autouse=True)
def outbound_http(monkeypatch):
    """
    No test reaches the network. The app's shared HTTP client is swapped for
    one that answers from a handler (outbound_http.respond_with(...)); without
    a handler, any outbound request fails the test.
    """
    fake = OutboundHttp()
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handle), timeout=http_client.TIMEOUT_SECONDS)
    monkeypatch.setattr(http_client, "_client", client)
    return fake


@pytest.fixture(autouse=True)
def quota_on_the_test_database(monkeypatch):
    """The free-quota guard counts in the test database, like everything else."""
    from app.services.quota import quota

    monkeypatch.setattr(quota, "bind", engine)


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
