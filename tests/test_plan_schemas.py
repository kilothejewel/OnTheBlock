"""The typed Plan contract: Stops are checked on save, old saved Plans still load, OpenAPI shows it."""

import pytest

from app.models.itinerary import Itinerary
from app.models.user import User
from app.services import itinerary as itinerary_module

PLAN = {
    "title": "A day out in Cape Town",
    "destination": "Cape Town",
    "budget": "$$",
    "duration_days": 1,
    "city": "cape-town",
    "currency": "ZAR",
    "items": [
        {
            "day": 1,
            "time": "09:00 AM",
            "activity": "Breakfast",
            "estimated_cost": 180,
            "location": "Test Bistro",
            "google_place_id": "ChIJabc123def456",
            "verified": True,
        }
    ],
}


def with_stop(**changes):
    return {**PLAN, "items": [{**PLAN["items"][0], **changes}]}


@pytest.mark.parametrize("budget", ["lots", "$$$$", ""])
def test_saving_a_plan_with_an_invalid_budget_is_rejected(client, auth_headers, budget):
    resp = client.post("/api/v1/itineraries/", json={**PLAN, "budget": budget}, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.parametrize("stop", [
    {"estimated_cost": -5},
    {"estimated_cost": 12.5},
    {"day": 0},
    {"activity": None},
])
def test_saving_a_plan_with_an_invalid_stop_is_rejected(client, auth_headers, stop):
    resp = client.post("/api/v1/itineraries/", json=with_stop(**stop), headers=auth_headers)
    assert resp.status_code == 422


def test_a_saved_stop_keeps_its_fields_and_drops_unknown_keys(client, auth_headers):
    resp = client.post("/api/v1/itineraries/", json=with_stop(_key="1-0", photo_url="https://x"), headers=auth_headers)

    assert resp.status_code == 201, resp.text
    stop = resp.json()["items"][0]
    assert stop["activity"] == "Breakfast"
    assert stop["estimated_cost"] == 180
    assert stop["verified"] is True
    assert "_key" not in stop and "photo_url" not in stop


def test_plans_saved_before_stops_were_typed_still_load(client, auth_headers, db_session):
    user = db_session.query(User).filter_by(username="tester").one()
    db_session.add(Itinerary(
        user_id=user.id,
        title="Old Plan",
        destination="Tokyo",
        budget="$$",
        duration_days=1,
        items=[
            {"day": 1, "activity": "Ramen", "estimated_cost": 12.75, "location": "Ichiran", "rating": 4.4},
            {"day": 1, "activity": "Walk", "estimated_cost": "free", "price_level": "PRICE_LEVEL_MODERATE"},
            {"day": 2, "description": "No activity key"},
        ],
    ))
    db_session.commit()

    resp = client.get("/api/v1/itineraries/", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    items = resp.json()[0]["items"]
    assert [item["estimated_cost"] for item in items] == [13, 0, 0]
    assert items[0]["rating"] == 4.4  # unknown keys from old Plans come back as they were
    assert items[1]["price_level"] is None
    assert items[2]["activity"] == ""


def test_costs_from_the_model_become_whole_non_negative_amounts():
    items = [
        {"activity": "Lunch", "estimated_cost": 14.6},
        {"activity": "Tip", "estimated_cost": -3},
        {"activity": "Walk", "estimated_cost": "about 10"},
        {"activity": "Park"},
    ]

    enriched = itinerary_module.itinerary_service._validate_and_enrich_items(items, {})

    assert [item["estimated_cost"] for item in enriched] == [15, 0, 0, 0]


def test_openapi_shows_the_stop_and_a_typed_generate_response(client):
    schema = client.get("/api/v1/openapi.json").json()

    stop = schema["components"]["schemas"]["Stop"]
    assert {"day", "activity", "estimated_cost", "google_place_id", "verified", "category"} <= set(stop["properties"])
    assert stop["properties"]["estimated_cost"]["minimum"] == 0

    generated = schema["paths"]["/api/v1/itineraries/generate"]["post"]["responses"]["200"]
    assert generated["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/GeneratedItinerary"}

    create = schema["components"]["schemas"]["ItineraryCreate"]
    assert create["properties"]["budget"]["enum"] == ["$", "$$", "$$$"]
