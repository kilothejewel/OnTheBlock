"""Per-user rate limits and the daily Plan quota (#43)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.rate_limit import limiter
from app.main import app
from app.services import plan_quota
from app.services import itinerary as itinerary_module

PLAN = {"city": "cape-town", "budget": "$$", "duration_days": 1}


def register(client, name):
    resp = client.post("/api/v1/auth/register", json={"email": f"{name}@example.com", "username": name, "password": "supersecret123"})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class Clock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at


@pytest.fixture
def clock(monkeypatch):
    clock = Clock(datetime(2026, 11, 20, 22, 30, tzinfo=timezone.utc))
    monkeypatch.setattr(plan_quota, "utc_now", clock)
    return clock


@pytest.fixture
def rate_limits_on():
    """The suite turns rate limiting off (conftest); these tests need it."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


class TestDailyPlanQuota:
    def test_the_sixth_plan_in_a_day_is_429_with_when_it_resets(self, client, auth_headers, clock):
        for _ in range(settings.PLANS_PER_USER_PER_DAY):
            assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).status_code == 200

        resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)

        assert resp.status_code == 429
        body = resp.json()
        assert body["limit"] == 5
        assert body["resets_at"] == "2026-11-21T00:00:00+00:00"
        assert "5 Plans today" in body["detail"]
        assert int(resp.headers["Retry-After"]) == 90 * 60 + 1  # 22:30 to midnight UTC

    def test_the_next_utc_day_works_again(self, client, auth_headers, clock):
        for _ in range(6):
            client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)
        clock.at = datetime(2026, 11, 21, 0, 0, 1, tzinfo=timezone.utc)
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).status_code == 200

    def test_each_user_has_their_own_quota(self, client, clock):
        alice, bob = register(client, "alice"), register(client, "bob")
        for _ in range(5):
            client.post("/api/v1/itineraries/generate", json=PLAN, headers=alice)
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=alice).status_code == 429
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=bob).status_code == 200

    def test_the_quota_survives_an_api_restart(self, client, auth_headers, clock, db_session):
        for _ in range(5):
            client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)
        # A fresh app lifespan against the same database: nothing carried over in memory.
        with TestClient(app) as after_restart:
            assert after_restart.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).status_code == 429
        assert db_session.execute(text("SELECT used FROM plan_quota_usage")).scalar() == 5

    def test_a_plan_that_fails_is_not_counted(self, client, auth_headers, clock, monkeypatch):
        async def broken(params):
            raise RuntimeError("Google is down")

        monkeypatch.setattr(itinerary_module.itinerary_service, "generate_itinerary", broken)
        for _ in range(8):
            assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).status_code == 500
        monkeypatch.undo()
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).status_code == 200

    def test_guests_get_their_own_lower_quota(self, db_session, clock):
        from app.models.user import User

        user = User(username="guest", email="guest@example.com", hashed_password="x")
        db_session.add(user)
        db_session.commit()
        user.is_guest = True  # #125 adds the column; the quota already reads it
        results = [plan_quota.take_plan(db_session, user).allowed for _ in range(settings.GUEST_PLANS_PER_DAY + 1)]
        assert results == [True] * settings.GUEST_PLANS_PER_DAY + [False]
        assert settings.GUEST_PLANS_PER_DAY < settings.PLANS_PER_USER_PER_DAY


class TestRateLimitsPerUser:
    def test_two_users_behind_one_ip_each_get_their_own_limit(self, client, rate_limits_on, clock, monkeypatch):
        monkeypatch.setattr(settings, "PLANS_PER_USER_PER_DAY", 100)
        alice, bob = register(client, "alice"), register(client, "bob")
        # The generate route allows 5 a minute; every TestClient request comes from one IP.
        statuses = [client.post("/api/v1/itineraries/generate", json=PLAN, headers=alice).status_code for _ in range(6)]
        assert statuses == [200] * 5 + [429]
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=bob).status_code == 200

    def test_requests_without_a_token_share_their_ips_limit(self, client, rate_limits_on):
        # Signed out, a route's own limit never runs (it's a 401 first); the
        # global 100 a minute applies, per IP. (It only covers routes on the
        # app itself today; see the PR's follow-ups.)
        statuses = [client.get("/").status_code for _ in range(101)]
        assert statuses[:100] == [200] * 100
        assert statuses[100] == 429

    def test_a_forged_token_counts_against_the_ip_not_a_user(self):
        from starlette.requests import Request
        from app.core.rate_limit import user_or_ip

        def request_with(auth):
            return Request({"type": "http", "headers": [(b"authorization", auth.encode())], "client": ("203.0.113.7", 1234)})

        assert user_or_ip(request_with("Bearer not.a.token")) == "ip:203.0.113.7"
        assert user_or_ip(request_with("")) == "ip:203.0.113.7"


@pytest.mark.parametrize("method, path", [
    ("POST", "/api/v1/itineraries/generate"),
    ("GET", "/api/v1/hotspots/recommend?query=cafes&city=cape-town"),
    ("GET", "/api/v1/places/ChIJabc123def456/photo"),
])
def test_requests_with_no_token_never_reach_google_or_an_llm(client, outbound_http, method, path, monkeypatch):
    from app.services.places import places_service

    monkeypatch.setattr(places_service, "api_key", "a-real-looking-key")
    llm_calls = []
    monkeypatch.setattr(itinerary_module.itinerary_service, "client", type("C", (), {"chat": property(lambda self: llm_calls.append(1))})())

    resp = client.request(method, path, json=PLAN if method == "POST" else None)

    assert resp.status_code == 401
    assert outbound_http.requests == []
    assert llm_calls == []


def api_routes():
    """(path, methods, dependency callables) for every API route, including those in included routers.

    FastAPI 0.16x keeps included routers as their own objects instead of copying
    their routes onto app.routes, so walk both.
    """
    from fastapi.routing import APIRoute

    def deps(dependant):
        for dep in dependant.dependencies:
            yield dep.call
            yield from deps(dep)

    for route in app.routes:
        contexts = route.effective_route_contexts() if hasattr(route, "effective_route_contexts") else [route] if isinstance(route, APIRoute) else []
        for ctx in contexts:
            yield ctx.path, set(ctx.methods or ()), set(deps(ctx.dependant))


def test_every_route_that_can_call_google_or_an_llm_needs_a_token():
    """Routes that reach Google or an LLM need an account or a guest session (#43, #125)."""
    from app.core.security import get_actor

    costly = {"/api/v1/itineraries/generate", "/api/v1/hotspots/recommend", "/api/v1/places/{place_id}/photo", "/api/v1/places"}
    found = {path: d for path, _, d in api_routes() if path in costly}
    assert set(found) == costly  # the walk really sees them
    for path, dependencies in found.items():
        assert get_actor in dependencies, path


def test_trips_and_saved_places_are_for_accounts_only():
    from app.core.security import require_account

    account_only = [(path, d) for path, _, d in api_routes() if path.startswith(("/api/v1/itineraries", "/api/v1/hotspots")) and path not in {"/api/v1/itineraries/generate", "/api/v1/hotspots/recommend"}]
    assert len(account_only) >= 6
    for path, dependencies in account_only:
        assert require_account in dependencies, path
