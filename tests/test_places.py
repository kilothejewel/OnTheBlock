"""
City-aware places: Google Places API (New) parsing, demo data per city and
photos. Google is never called: either the service's _request is replaced with
a fake (live_google), or the shared HTTP client answers for Google (google).
"""

import asyncio

import httpx
import pytest

from app.core.cities import get_city
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


DETAILS_PHOTO = {
    "name": "places/ChIJxyz789uvw012/photos/PHOTO2",
    "authorAttributions": [{"displayName": "Thandi Snaps", "uri": "https://maps.google.com/thandi"}],
}


@pytest.fixture
def google(monkeypatch, outbound_http):
    """Pretend a real key is set, and let the shared HTTP client answer as Google would."""

    def respond(request):
        path = request.url.path
        if path == "/v1/places:searchText":
            return httpx.Response(200, json={"places": [GOOGLE_PLACE]})
        if path == "/v1/places/ChIJxyz789uvw012":
            return httpx.Response(200, json={"photos": [DETAILS_PHOTO]})
        if path.endswith("/media"):
            return httpx.Response(200, json={"photoUri": "https://lh3.googleusercontent.com/photo"})
        return httpx.Response(404, json={"error": {"message": "Not found"}})

    outbound_http.respond_with(respond)
    monkeypatch.setattr(places_service, "api_key", "test-key")
    monkeypatch.setattr(places_service, "_photo_refs", {})
    monkeypatch.setattr(places_service, "_photo_urls", {})
    return outbound_http


def test_every_google_request_goes_through_the_shared_client(client, auth_headers, google, monkeypatch):
    clients_created = []
    create_client = httpx.AsyncClient.__init__

    def count_new_clients(self, *args, **kwargs):
        clients_created.append(self)
        create_client(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", count_new_clients)

    search = client.get("/api/v1/hotspots/recommend?query=brunch&city=cape-town", headers=auth_headers)
    photo_from_search = client.get("/api/v1/places/ChIJabc123def456/photo", headers=auth_headers)
    photo_from_details = client.get("/api/v1/places/ChIJxyz789uvw012/photo", headers=auth_headers)

    assert [place["name"] for place in search.json()] == ["Test Bistro"]
    assert photo_from_search.json()["attribution"] == "Sam Lens"
    assert photo_from_details.json()["attribution"] == "Thandi Snaps"
    assert [(request.method, request.url.path) for request in google.requests] == [
        ("POST", "/v1/places:searchText"),
        ("GET", "/v1/places/ChIJabc123def456/photos/PHOTO1/media"),
        ("GET", "/v1/places/ChIJxyz789uvw012"),
        ("GET", "/v1/places/ChIJxyz789uvw012/photos/PHOTO2/media"),
    ]
    assert all(request.url.host == "places.googleapis.com" for request in google.requests)
    assert all(request.headers["X-Goog-Api-Key"] == "test-key" for request in google.requests)
    assert clients_created == []  # no call opened a client of its own


@pytest.mark.parametrize("failure", [httpx.ConnectError("no route to host"), httpx.ReadTimeout("timed out")])
def test_google_being_unreachable_is_a_clear_502(client, auth_headers, google, failure):
    def fail(request):
        raise failure

    google.respond_with(fail)

    resp = client.get("/api/v1/hotspots/recommend?query=cafes&city=london", headers=auth_headers)

    assert resp.status_code == 502
    assert str(failure) not in resp.json()["detail"]  # internals stay on the server


def test_google_refusing_a_request_is_a_clear_502(client, auth_headers, google):
    google.respond_with(lambda request: httpx.Response(429, json={"error": {"message": "Quota exceeded"}}))

    resp = client.get("/api/v1/hotspots/recommend?query=cafes&city=london", headers=auth_headers)

    assert resp.status_code == 502
    assert "Quota" not in resp.json()["detail"]


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
