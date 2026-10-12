"""
City-aware places: Google Places API (New) parsing, demo data per city,
photos, and the column stopgap. Google is never called: the service's
_request is replaced with a fake.
"""

import asyncio

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core.cities import get_city
from app.core.database import add_missing_columns
from app.services.places import PlacesError, parse_place, places_service

GOOGLE_PLACE = {
    "id": "ChIJabc123def456",
    "displayName": {"text": "Test Bistro"},
    "formattedAddress": "1 Long St, Cape Town",
    "location": {"latitude": -33.92, "longitude": 18.42},
    "rating": 4.6,
    "userRatingCount": 812,
    "priceLevel": "PRICE_LEVEL_MODERATE",
    "types": ["restaurant", "food"],
    "photos": [
        {
            "name": "places/ChIJabc123def456/photos/PHOTO1",
            "authorAttributions": [{"displayName": "Sam Lens", "uri": "https://maps.google.com/sam"}],
        }
    ],
}


@pytest.fixture
def live_google(monkeypatch):
    """Pretend a real key is set and answer requests from a fake Google."""
    calls = []

    async def fake_request(method, path, *, field_mask=None, json=None, params=None):
        calls.append((method, path, json))
        if path == "places:searchText":
            return {"places": [GOOGLE_PLACE]}
        if path.endswith("/media"):
            return {"photoUri": "https://lh3.googleusercontent.com/photo1"}
        raise AssertionError(f"unexpected request {path}")

    monkeypatch.setattr(places_service, "api_key", "test-key")
    monkeypatch.setattr(places_service, "_request", fake_request)
    monkeypatch.setattr(places_service, "_photo_refs", {})
    monkeypatch.setattr(places_service, "_photo_urls", {})
    return calls


def test_parse_place_maps_the_new_api_shape():
    place = parse_place(GOOGLE_PLACE)
    assert place == {
        "google_place_id": "ChIJabc123def456",
        "name": "Test Bistro",
        "rating": 4.6,
        "user_rating_count": 812,
        "address": "1 Long St, Cape Town",
        "latitude": -33.92,
        "longitude": 18.42,
        "price_level": 2,
        "types": "restaurant, food",
    }


def test_live_search_is_biased_to_the_city(live_google):
    places = asyncio.run(places_service.search_places("brunch", get_city("cape-town")))
    assert [p["name"] for p in places] == ["Test Bistro"]

    _, _, body = live_google[0]
    assert body["textQuery"] == "brunch in Cape Town"
    assert body["regionCode"] == "ZA"
    assert body["locationBias"]["circle"]["center"]["latitude"] == pytest.approx(-33.9249)


def test_search_failure_returns_a_clear_502(client, auth_headers, monkeypatch):
    async def failing_search(query, city):
        raise PlacesError("quota exceeded")

    monkeypatch.setattr(places_service, "search_places", failing_search)
    resp = client.get("/api/v1/hotspots/recommend?query=cafes&city=london", headers=auth_headers)
    assert resp.status_code == 502
    assert "quota" not in resp.json()["detail"]  # internals stay on the server


def test_demo_search_returns_the_requested_city(client, auth_headers):
    resp = client.get("/api/v1/hotspots/recommend?query=coffee&city=tokyo", headers=auth_headers)
    assert resp.status_code == 200
    places = resp.json()
    assert all(p["google_place_id"].startswith("mock_tokyo_") for p in places)
    assert all(p["address"].endswith("Tokyo") for p in places)
    assert "coffee" in places[0]["types"]  # matches come first


def test_unknown_city_is_rejected(client, auth_headers):
    resp = client.get("/api/v1/hotspots/recommend?query=coffee&city=paris", headers=auth_headers)
    assert resp.status_code == 422


def test_demo_itinerary_matches_city_and_currency(client, auth_headers):
    resp = client.post(
        "/api/v1/itineraries/generate",
        json={"city": "cape-town", "budget": "$$", "duration_days": 2, "preferences": "food, nightlife"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["destination"] == "Cape Town"
    assert plan["currency"] == "ZAR"
    assert plan["demo"] is True
    assert all(item["address"].endswith("Cape Town") for item in plan["items"])
    assert any(item["activity"] == "Night out" for item in plan["items"])

    for day in (1, 2):
        meals = [i["location"] for i in plan["items"] if i["day"] == day and i["activity"] in ("Lunch", "Dinner")]
        assert len(meals) == len(set(meals)), "lunch and dinner should be different places"


def test_barbecue_does_not_count_as_nightlife(client, auth_headers):
    resp = client.post(
        "/api/v1/itineraries/generate",
        json={"city": "johannesburg", "budget": "$", "duration_days": 1, "preferences": "barbecue"},
        headers=auth_headers,
    )
    assert all(item["activity"] != "Night out" for item in resp.json()["items"])


@pytest.mark.parametrize(
    "payload",
    [
        {"city": "tokyo", "budget": "lots", "duration_days": 1},
        {"city": "tokyo", "budget": "$", "duration_days": 9},
        {"city": "atlantis", "budget": "$", "duration_days": 1},
        {"city": "tokyo", "budget": "$", "duration_days": 1, "preferences": "x" * 201},
    ],
)
def test_generate_rejects_invalid_requests(client, auth_headers, payload):
    resp = client.post("/api/v1/itineraries/generate", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_saved_itinerary_keeps_city_and_currency(client, auth_headers):
    payload = {
        "title": "A day out in Tokyo",
        "destination": "Tokyo",
        "budget": "$",
        "duration_days": 1,
        "city": "tokyo",
        "currency": "JPY",
        "items": [{"day": 1, "activity": "Explore", "estimated_cost": 1500}],
    }
    saved = client.post("/api/v1/itineraries/", json=payload, headers=auth_headers).json()
    assert saved["currency"] == "JPY"
    assert saved["city"] == "tokyo"


def test_photo_requires_login(client):
    assert client.get("/api/v1/places/ChIJabc123def456/photo").status_code == 401


def test_demo_places_have_no_photo(client, auth_headers):
    assert client.get("/api/v1/places/mock_tokyo_1/photo", headers=auth_headers).status_code == 404


def test_photo_comes_from_search_and_is_cached(client, auth_headers, live_google):
    asyncio.run(places_service.search_places("brunch", get_city("cape-town")))

    first = client.get("/api/v1/places/ChIJabc123def456/photo", headers=auth_headers)
    assert first.status_code == 200
    assert first.json() == {
        "url": "https://lh3.googleusercontent.com/photo1",
        "attribution": "Sam Lens",
        "attribution_url": "https://maps.google.com/sam",
    }

    client.get("/api/v1/places/ChIJabc123def456/photo", headers=auth_headers)
    media_calls = [c for c in live_google if c[1].endswith("/media")]
    assert len(media_calls) == 1  # second request served from the cache


def test_add_missing_columns_upgrades_an_existing_table():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE itineraries (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
            "title VARCHAR NOT NULL, destination VARCHAR NOT NULL, budget VARCHAR NOT NULL, "
            "duration_days INTEGER, items JSON NOT NULL, created_at DATETIME)"
        ))

    add_missing_columns(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("itineraries")}
    assert {"city", "currency"} <= columns
