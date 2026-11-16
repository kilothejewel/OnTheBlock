"""The city search box's API side (#89): aliases on /cities and city requests."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.core.cities import CITIES
from app.routers import city_requests


@pytest.fixture
def clock(monkeypatch):
    now = {"at": datetime(2026, 11, 20, 23, 0)}
    monkeypatch.setattr(city_requests, "utc_now", lambda: now["at"])
    return now


def test_joburg_and_jozi_are_aliases_of_johannesburg(client):
    joburg = next(c for c in client.get("/api/v1/cities").json() if c["slug"] == "johannesburg")
    assert {"Joburg", "Jozi"} <= set(joburg["aliases"])


def test_every_south_african_city_has_aliases_and_none_clash():
    seen = {}
    for city in CITIES.values():
        for name in (city.name, *city.aliases):
            assert seen.setdefault(name.lower(), city.slug) == city.slug, name
    assert all(CITIES[s].aliases for s in ("cape-town", "johannesburg", "durban", "pretoria", "stellenbosch"))


def test_a_request_is_stored_with_the_user_and_time(client, auth_headers, db_session, clock):
    resp = client.post("/api/v1/city-requests", json={"text": "  Port   Elizabeth "}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["text"] == "Port Elizabeth"
    row = db_session.execute(text("SELECT text, user_id, created_at FROM city_requests")).one()
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    assert row.text == "Port Elizabeth" and row.user_id == me["id"]
    assert str(row.created_at).startswith("2026-11-20 23:00")


def test_guests_can_ask_for_a_city(client):
    token = client.post("/api/v1/auth/guest").json()["access_token"]
    assert client.post("/api/v1/city-requests", json={"text": "Gqeberha"}, headers={"Authorization": f"Bearer {token}"}).status_code == 201


def test_signing_in_is_needed(client):
    assert client.post("/api/v1/city-requests", json={"text": "Bloemfontein"}).status_code in (401, 403)


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "   "}, {"text": "x" * 81}, {}])
def test_empty_or_long_text_is_refused(client, auth_headers, body):
    assert client.post("/api/v1/city-requests", json=body, headers=auth_headers).status_code == 422


def test_the_sixth_request_in_a_utc_day_is_429_and_the_next_day_resets(client, auth_headers, clock):
    for name in ["Polokwane", "Kimberley", "Nelspruit", "East London", "George"]:
        assert client.post("/api/v1/city-requests", json={"text": name}, headers=auth_headers).status_code == 201
    resp = client.post("/api/v1/city-requests", json={"text": "Knysna"}, headers=auth_headers)
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "3600"

    clock["at"] = datetime(2026, 11, 21, 0, 1)
    assert client.post("/api/v1/city-requests", json={"text": "Knysna"}, headers=auth_headers).status_code == 201


def test_one_users_requests_dont_use_up_anothers(client, auth_headers, clock):
    for i in range(5):
        client.post("/api/v1/city-requests", json={"text": f"Town {i}"}, headers=auth_headers)
    other = client.post("/api/v1/auth/register", json={"email": "lerato@example.com", "username": "lerato", "password": "supersecret123"})
    headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    assert client.post("/api/v1/city-requests", json={"text": "Knysna"}, headers=headers).status_code == 201


def test_requests_outlive_the_user_for_demand_counts(db_session):
    from sqlalchemy import inspect

    (fk,) = inspect(db_session.get_bind()).get_foreign_keys("city_requests")
    assert (fk["referred_table"], fk["options"].get("ondelete")) == ("users", "SET NULL")


def test_the_admin_query_counts_requests_per_city(client, auth_headers, db_session):
    for name in ["Hermanus", "hermanus ", "Knysna"]:
        client.post("/api/v1/city-requests", json={"text": name}, headers=auth_headers)
    rows = db_session.execute(text(
        "SELECT lower(text) AS city, count(*) AS requests, count(DISTINCT user_id) AS people, max(created_at) AS latest "
        "FROM city_requests GROUP BY lower(text) ORDER BY requests DESC, city"
    )).all()
    assert [(r.city, r.requests, r.people) for r in rows] == [("hermanus", 2, 1), ("knysna", 1, 1)]
