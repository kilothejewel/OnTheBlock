"""No silent Demo data (#42, ADR 0003): with keys set, failures are honest errors or real Plans."""

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.routers import itineraries as itineraries_router
from app.services import itinerary as itinerary_module
from app.services import llm as llm_module
from app.services.llm import GeminiLLMClient, GroqLLMClient, LLMChain, RulesLLMClient

PLAN = {"city": "cape-town", "budget": "$$", "duration_days": 1}
PLACE = {"google_place_id": "ChIJreal0000001", "name": "Real Bistro", "rating": 4.6, "address": "1 Long St, Cape Town",
         "price_level": 2, "latitude": -33.92, "longitude": 18.42}


class AllowAll:
    def take(self, *args, **kwargs):
        return True


class BrokenOpenAI:
    class chat:
        class completions:
            @staticmethod
            async def create(**kwargs):
                raise RuntimeError("OpenAI is down")


@pytest.fixture
def live_keys(monkeypatch):
    """Keys set: Google live, OpenAI configured."""
    monkeypatch.setattr(itinerary_module.places_service, "api_key", "test-key")
    monkeypatch.setattr(itinerary_module.itinerary_service, "client", BrokenOpenAI())


def test_with_keys_set_an_unreachable_google_is_a_503_never_demo_data(client, auth_headers, live_keys, outbound_http):
    outbound_http.respond_with(lambda request: (_ for _ in ()).throw(httpx.ConnectError("no route to host")))

    resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "places_unavailable" and body["retryable"] is True
    assert "Cape Town" in body["message"] and body["detail"] == body["message"]
    assert "demo" not in resp.text.lower()
    assert resp.headers["Retry-After"]


def test_a_503_does_not_use_up_the_daily_plan_quota(client, auth_headers, live_keys, monkeypatch):
    async def nothing(city, category, budget, max_results=5):
        return []

    monkeypatch.setattr(itinerary_module.places_service, "search_places_for_slot", nothing)
    for _ in range(8):
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).status_code == 503


def test_every_llm_provider_failing_still_returns_a_real_plan_from_the_rules_client(client, auth_headers, live_keys, monkeypatch, outbound_http):
    async def real_places(city, category, budget, max_results=5):
        return [{**PLACE, "google_place_id": f"ChIJ{category}000001", "name": f"Real {category.title()}"}]

    monkeypatch.setattr(itinerary_module.places_service, "search_places_for_slot", real_places)
    # Gemini and Groq both configured, both down.
    outbound_http.respond_with(lambda request: httpx.Response(503, json={}))
    chain = LLMChain([GeminiLLMClient(api_key="gk"), GroqLLMClient(api_key="qk"), RulesLLMClient()], quota=AllowAll())
    monkeypatch.setattr(itinerary_module, "llm", chain)

    async def instant(_):
        return None
    monkeypatch.setattr(llm_module.asyncio, "sleep", instant)

    resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    plan = resp.json()
    assert plan["demo"] is False
    assert [item["location"] for item in plan["items"]] == ["Real Breakfast", "Real Lunch", "Real Dinner"]
    assert all(item["verified"] and item["google_place_id"].startswith("ChIJ") for item in plan["items"])
    assert {r.url.host for r in outbound_http.requests} == {"generativelanguage.googleapis.com", "api.groq.com"}


def test_with_a_google_key_but_no_openai_key_the_free_chain_plans(client, auth_headers, monkeypatch):
    async def real_places(city, category, budget, max_results=5):
        return [{**PLACE, "google_place_id": f"ChIJ{category}000002"}]

    monkeypatch.setattr(itinerary_module.places_service, "api_key", "test-key")
    monkeypatch.setattr(itinerary_module.places_service, "search_places_for_slot", real_places)
    monkeypatch.setattr(itinerary_module.itinerary_service, "client", None)
    monkeypatch.setattr(itinerary_module, "llm", LLMChain([RulesLLMClient()], quota=AllowAll()))

    plan = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).json()

    assert plan["demo"] is False and len(plan["items"]) == 3


def test_without_keys_demo_data_is_still_served_and_labelled(client, auth_headers):
    plan = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers).json()
    assert plan["demo"] is True
    assert all(item["google_place_id"].startswith("mock_") for item in plan["items"])


def test_an_unreachable_database_is_a_readable_503(client, auth_headers, monkeypatch):
    def database_down(db, user):
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server"))

    monkeypatch.setattr(itineraries_router, "take_plan", database_down)

    resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)

    assert resp.status_code == 503
    assert resp.json()["code"] == "database_unavailable"
    assert "could not connect" not in resp.text  # internals stay on the server
