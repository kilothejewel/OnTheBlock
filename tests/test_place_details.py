"""GET /places?ids= (#29): batched Pro-SKU details, quota-guarded, with catalogue and Demo fallbacks."""

import httpx
import pytest

from app.models.place import Place
from app.services.places import DETAILS_FIELD_MASK, DETAILS_PRO_FIELDS, places_service
from app.services.quota import quota

# Place Details (New) fields billed above Pro: none of these may be asked for here.
ENTERPRISE_FIELDS = {"rating", "userRatingCount", "regularOpeningHours", "currentOpeningHours", "priceLevel",
                     "priceRange", "websiteUri", "nationalPhoneNumber", "internationalPhoneNumber", "reviews",
                     "editorialSummary", "servesBeer", "outdoorSeating"}


def details_reply(request):
    place_id = request.url.path.rsplit("/", 1)[-1]
    return httpx.Response(200, json={
        "id": place_id, "displayName": {"text": f"Place {place_id[-2:]}"}, "formattedAddress": "1 Long St, Cape Town",
        "location": {"latitude": -33.92, "longitude": 18.42}, "types": ["restaurant"], "googleMapsUri": f"https://maps.google.com/?cid={place_id}",
    })


@pytest.fixture
def google(monkeypatch, outbound_http):
    monkeypatch.setattr(places_service, "api_key", "test-key")
    outbound_http.respond_with(details_reply)
    return outbound_http


def ids(n, prefix="ChIJplace0000"):
    return [f"{prefix}{i:02d}" for i in range(n)]


def test_one_request_returns_details_for_up_to_20_places(client, auth_headers, google):
    resp = client.get(f"/api/v1/places?ids={','.join(ids(20))}", headers=auth_headers)
    assert resp.status_code == 200
    places = resp.json()
    assert [p["google_place_id"] for p in places] == ids(20)
    assert places[0] == {
        "google_place_id": "ChIJplace000000", "name": "Place 00", "address": "1 Long St, Cape Town",
        "latitude": -33.92, "longitude": 18.42, "types": ["restaurant"], "maps_url": "https://maps.google.com/?cid=ChIJplace000000",
        "area": None, "source": "google", "details_available": True,
    }
    assert len(google.requests) == 20


def test_more_than_20_is_a_422(client, auth_headers, google):
    resp = client.get(f"/api/v1/places?ids={','.join(ids(21))}", headers=auth_headers)
    assert resp.status_code == 422 and "At most 20" in resp.json()["detail"]
    assert google.requests == []


def test_duplicate_ids_are_fetched_once(client, auth_headers, google):
    one = "ChIJplace000001"
    resp = client.get(f"/api/v1/places?ids={one},{one},{one}", headers=auth_headers)
    assert [p["google_place_id"] for p in resp.json()] == [one]
    assert len(google.requests) == 1


def test_the_field_mask_stays_on_the_pro_sku(client, auth_headers, google):
    client.get(f"/api/v1/places?ids={ids(1)[0]}", headers=auth_headers)
    sent = set(google.requests[0].headers["X-Goog-FieldMask"].split(","))
    assert sent == set(DETAILS_PRO_FIELDS)
    assert not sent & ENTERPRISE_FIELDS
    assert not set(DETAILS_FIELD_MASK.split(",")) & ENTERPRISE_FIELDS


def test_quota_refused_gives_catalogue_fields_and_no_google_call(client, auth_headers, google, db_session, monkeypatch):
    db_session.add(Place(city="cape-town", name="Truth Coffee Roasting", lat=-33.9278, lng=18.4232, area_id="city-bowl",
                         categories=["coffee_shop"], interests=["coffee"], overture_id="ov3", google_place_id="ChIJtruth00001"))
    db_session.commit()
    monkeypatch.setattr(quota, "take", lambda resource, n=1, pool="users": False)

    resp = client.get("/api/v1/places?ids=ChIJtruth00001,ChIJnotincatalog1", headers=auth_headers)

    assert resp.status_code == 200
    truth, unknown = resp.json()
    assert (truth["name"], truth["area"], truth["source"], truth["details_available"]) == ("Truth Coffee Roasting", "city-bowl", "catalogue", False)
    assert truth["address"] is None  # no Google field without Google
    assert (unknown["source"], unknown["details_available"]) == ("unknown", False)
    assert google.requests == []


def test_each_google_call_takes_from_the_details_pro_quota(client, auth_headers, google, monkeypatch):
    taken = []
    monkeypatch.setattr(quota, "take", lambda resource, n=1, pool="users": taken.append((resource, pool)) or True)
    client.get(f"/api/v1/places?ids={','.join(ids(3))}", headers=auth_headers)
    assert taken == [("google.details_pro", "users")] * 3


def test_a_google_failure_falls_back_to_the_catalogue(client, auth_headers, google):
    google.respond_with(lambda request: httpx.Response(503, json={}))
    [place] = client.get(f"/api/v1/places?ids={ids(1)[0]}", headers=auth_headers).json()
    assert place["details_available"] is False


def test_demo_ids_return_demo_data_labelled(client, auth_headers, google):
    [demo] = client.get("/api/v1/places?ids=mock_cape-town_1", headers=auth_headers).json()
    assert (demo["name"], demo["source"], demo["details_available"]) == ("Truth Coffee Roasting", "demo", True)
    assert google.requests == []


def test_it_needs_a_signed_in_user(client):
    assert client.get("/api/v1/places?ids=ChIJplace000000").status_code == 401


def test_photos_take_from_the_photo_quota_and_stop_when_refused(client, auth_headers, google, monkeypatch):
    monkeypatch.setattr(places_service, "_photo_refs", {"ChIJphoto00001": {"name": "places/ChIJphoto00001/photos/P1"}})
    monkeypatch.setattr(places_service, "_photo_urls", {})
    monkeypatch.setattr(quota, "take", lambda resource, n=1, pool="users": resource != "google.photos")
    assert client.get("/api/v1/places/ChIJphoto00001/photo", headers=auth_headers).status_code == 404
    assert google.requests == []
