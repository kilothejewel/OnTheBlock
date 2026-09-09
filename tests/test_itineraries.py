"""
Itinerary tests.

`/itineraries/generate` fans out to Google Places and OpenAI. Both are mocked
here so the real grounding/validation logic in ItineraryService runs against
deterministic inputs without any network calls.
"""

import json

import pytest

from app.services import itinerary as itinerary_module

CANDIDATE = {
    "google_place_id": "place_abc",
    "name": "Test Diner",
    "rating": 4.5,
    "address": "1 Test St, Testville",
    "price_level": 2,
}


class _FakeOpenAI:
    """Minimal stand-in for the OpenAI client used in ItineraryService."""

    def __init__(self, content: str):
        payload = content

        class _Completions:
            def create(self, *args, **kwargs):
                message = type("Msg", (), {"content": payload})
                choice = type("Choice", (), {"message": message})
                return type("Resp", (), {"choices": [choice]})

        self.chat = type("Chat", (), {"completions": _Completions()})


@pytest.fixture
def mock_itinerary_backends(monkeypatch):
    async def fake_search_places_for_slot(destination, category, budget, max_results=5):
        return [CANDIDATE]

    monkeypatch.setattr(
        itinerary_module.places_service,
        "search_places_for_slot",
        fake_search_places_for_slot,
    )

    gpt_response = json.dumps(
        {
            "title": "A Day in Testville",
            "destination": "Testville",
            "budget": "$$",
            "duration_days": 1,
            "items": [
                {
                    "day": 1,
                    "time": "09:00 AM",
                    "activity": "Breakfast at Test Diner",
                    "description": "Start the day with pancakes.",
                    "estimated_cost": 15,
                    "location": "Test Diner",
                    "google_place_id": "place_abc",
                },
                {
                    "day": 1,
                    "time": "12:00 PM",
                    "activity": "Walk in the park",
                    "description": "A stroll with no specific venue.",
                    "estimated_cost": 0,
                    "location": "Central Park",
                    "google_place_id": None,
                },
            ],
        }
    )
    monkeypatch.setattr(
        itinerary_module.itinerary_service, "client", _FakeOpenAI(gpt_response)
    )


def test_generate_itinerary_is_grounded_in_candidates(
    client, auth_headers, mock_itinerary_backends
):
    resp = client.post(
        "/api/v1/itineraries/generate",
        json={"destination": "Testville", "budget": "$$", "duration_days": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "A Day in Testville"

    verified = data["items"][0]
    assert verified["google_place_id"] == "place_abc"
    assert verified["verified"] is True
    assert verified["address"] == CANDIDATE["address"]

    generic = data["items"][1]
    assert generic["google_place_id"] is None
    assert generic["verified"] is False


def test_validate_and_enrich_marks_verified_and_unverified():
    """Unit-test the grounding logic directly (no HTTP, no mocks needed)."""
    candidate_lookup = {"place_abc": CANDIDATE}
    items = [
        {"activity": "Breakfast", "location": "Test Diner", "google_place_id": "place_abc"},
        {"activity": "Lunch", "location": "Ghost Kitchen", "google_place_id": "hallucinated_id"},
        {"activity": "Evening stroll", "location": "Riverside", "google_place_id": None},
    ]

    enriched = itinerary_module.itinerary_service._validate_and_enrich_items(
        items, candidate_lookup
    )

    # matching place_id -> verified, address filled in from the candidate
    assert enriched[0]["verified"] is True
    assert enriched[0]["google_place_id"] == "place_abc"
    assert enriched[0]["address"] == CANDIDATE["address"]

    # unmatched place_id -> unverified, id dropped, "[Unverified]" prefix on location
    assert enriched[1]["verified"] is False
    assert enriched[1]["google_place_id"] is None
    assert enriched[1]["location"] == "[Unverified] Ghost Kitchen"

    # no place_id -> left as a generic activity, unverified
    assert enriched[2]["verified"] is False
    assert enriched[2]["google_place_id"] is None


def test_generate_itinerary_requires_auth(client):
    resp = client.post(
        "/api/v1/itineraries/generate",
        json={"destination": "Testville", "budget": "$$", "duration_days": 1},
    )
    assert resp.status_code == 401


def test_save_list_get_delete_itinerary(client, auth_headers):
    payload = {
        "title": "Weekend Trip",
        "destination": "Testville",
        "budget": "$$",
        "duration_days": 2,
        "items": [{"day": 1, "activity": "Explore", "google_place_id": None}],
    }

    created = client.post("/api/v1/itineraries/", json=payload, headers=auth_headers)
    assert created.status_code == 201
    itinerary_id = created.json()["id"]

    listed = client.get("/api/v1/itineraries/", headers=auth_headers)
    assert listed.status_code == 200
    assert [i["id"] for i in listed.json()] == [itinerary_id]

    fetched = client.get(f"/api/v1/itineraries/{itinerary_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Weekend Trip"

    deleted = client.delete(f"/api/v1/itineraries/{itinerary_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/itineraries/", headers=auth_headers).json() == []


def test_itinerary_access_is_per_user(client, auth_headers):
    payload = {
        "title": "Private Trip",
        "destination": "Testville",
        "budget": "$",
        "duration_days": 1,
        "items": [{"day": 1, "activity": "Explore", "google_place_id": None}],
    }
    itinerary_id = client.post(
        "/api/v1/itineraries/", json=payload, headers=auth_headers
    ).json()["id"]

    other_token = client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "username": "bob", "password": "supersecret123"},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.get(
        f"/api/v1/itineraries/{itinerary_id}", headers=other_headers
    ).status_code == 404
