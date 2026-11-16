"""Structured logging, request IDs, call counts and error tracking (#26)."""

import ast
import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core import observability
from app.core.observability import JsonFormatter, REQUEST_ID_HEADER, configure_error_tracking
from app.main import app
from app.services.places import places_service

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def request_logs(caplog):
    return [r for r in caplog.records if r.name == "app.request" and r.getMessage() == "request"]


def test_no_print_is_left_in_the_app():
    printed = []
    for path in APP_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                printed.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")
    assert printed == []


class TestRequestId:
    def test_every_response_carries_one(self, client):
        first, second = client.get("/health"), client.get("/api/v1/cities")
        assert len(first.headers[REQUEST_ID_HEADER]) == 32
        assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]

    def test_error_responses_carry_one_too(self, client):
        assert client.get("/api/v1/itineraries/").headers.get(REQUEST_ID_HEADER)  # 401
        assert client.get("/api/v1/nowhere").headers.get(REQUEST_ID_HEADER)  # 404
        assert client.post("/api/v1/auth/register", json={}).headers.get(REQUEST_ID_HEADER)  # 422

    def test_a_sane_incoming_id_is_kept_and_anything_else_replaced(self, client):
        assert client.get("/health", headers={REQUEST_ID_HEADER: "render-abc-12345678"}).headers[REQUEST_ID_HEADER] == "render-abc-12345678"
        for bad in ["short", "x" * 65, "has spaces in it ok", "<script>alert(1)</script>"]:
            assert client.get("/health", headers={REQUEST_ID_HEADER: bad}).headers[REQUEST_ID_HEADER] != bad

    def test_the_browser_may_read_it(self, client):
        resp = client.get("/health", headers={"Origin": "http://localhost:5273"})
        assert REQUEST_ID_HEADER.lower() in resp.headers["access-control-expose-headers"].lower()

    def test_it_is_on_the_requests_log_lines(self, client, caplog):
        caplog.set_level(logging.INFO)
        resp = client.get("/health")
        [line] = request_logs(caplog)
        assert line.request_id == resp.headers[REQUEST_ID_HEADER]
        assert (line.method, line.path, line.status) == ("GET", "/health", 200)
        assert line.duration_ms >= 0

    def test_log_lines_outside_a_request_have_none(self, caplog):
        caplog.set_level(logging.INFO)
        logging.getLogger("app.test").info("background job")
        assert caplog.records[-1].request_id is None


class TestJsonLines:
    def test_a_record_is_one_json_object_with_its_extra_fields(self):
        record = logging.LogRecord("app.x", logging.WARNING, __file__, 1, "places search failed", None, None)
        record.request_id, record.city = "abc12345", "cape-town"
        entry = json.loads(JsonFormatter().format(record))
        assert entry["level"] == "WARNING"
        assert entry["message"] == "places search failed"
        assert (entry["request_id"], entry["city"]) == ("abc12345", "cape-town")
        assert entry["time"].endswith("+00:00")

    def test_exceptions_are_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = logging.LogRecord("app.x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
        assert "ValueError: boom" in json.loads(JsonFormatter().format(record))["exception"]


class TestCallCounts:
    def test_google_calls_are_counted_per_request(self, client, auth_headers, outbound_http, monkeypatch, caplog):
        outbound_http.respond_with(lambda request: httpx.Response(200, json={"places": []}))
        monkeypatch.setattr(places_service, "api_key", "test-key")
        caplog.set_level(logging.INFO)

        client.get("/api/v1/hotspots/recommend?query=coffee&city=cape-town", headers=auth_headers)
        client.get("/health")

        search, health = request_logs(caplog)[-2:]
        assert (search.google_calls, health.google_calls) == (1, 0)

    def test_plan_generation_logs_its_google_and_llm_calls_by_provider(self, client, auth_headers, monkeypatch, caplog):
        from app.services import itinerary as itinerary_module

        async def fake_slot(city, category, budget, max_results=5):
            observability.count_call("google")
            return []

        class FakeOpenAI:
            class chat:
                class completions:
                    @staticmethod
                    async def create(**kwargs):
                        message = type("M", (), {"content": json.dumps({"title": "t", "items": []})})
                        return type("R", (), {"choices": [type("C", (), {"message": message})]})

        monkeypatch.setattr(itinerary_module.places_service, "search_places_for_slot", fake_slot)
        monkeypatch.setattr(itinerary_module.itinerary_service, "client", FakeOpenAI())
        caplog.set_level(logging.INFO)

        resp = client.post("/api/v1/itineraries/generate", json={"city": "cape-town", "budget": "$$", "duration_days": 1}, headers=auth_headers)

        assert resp.status_code == 200, resp.text
        [plan] = [r for r in caplog.records if r.getMessage() == "plan generated"]
        assert plan.google_calls == 3  # breakfast, lunch, dinner
        assert plan.llm_calls == {"openai": 1}
        assert plan.request_id == resp.headers[REQUEST_ID_HEADER]

    def test_a_demo_plan_makes_no_calls(self, client, auth_headers, caplog):
        caplog.set_level(logging.INFO)
        client.post("/api/v1/itineraries/generate", json={"city": "durban", "budget": "$", "duration_days": 1}, headers=auth_headers)
        [plan] = [r for r in caplog.records if r.getMessage() == "plan generated"]
        assert (plan.google_calls, plan.llm_calls, plan.demo) == (0, {}, True)


class TestErrorTracking:
    @pytest.fixture
    def broken_route(self):
        router = APIRouter()

        @router.get("/__boom")
        def boom():
            raise RuntimeError("database fell over")

        app.include_router(router)
        yield "/__boom"
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/__boom"]

    def test_an_unhandled_error_is_a_500_with_a_request_id_and_reaches_the_tracker(self, broken_route, monkeypatch, caplog):
        import sentry_sdk

        captured = []
        monkeypatch.setattr(sentry_sdk, "is_initialized", lambda: True)
        monkeypatch.setattr(sentry_sdk, "capture_exception", captured.append)
        caplog.set_level(logging.INFO)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(broken_route)

        assert resp.status_code == 500
        assert "database fell over" not in resp.text  # internals stay on the server
        assert resp.headers[REQUEST_ID_HEADER]
        assert [type(e) for e in captured] == [RuntimeError]
        [error] = [r for r in caplog.records if r.getMessage() == "unhandled error"]
        assert error.request_id == resp.headers[REQUEST_ID_HEADER] and error.exc_info

    def test_the_tracker_is_off_without_a_dsn(self, monkeypatch):
        import sentry_sdk

        calls = []
        monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
        assert configure_error_tracking(None) is False
        assert configure_error_tracking("") is False
        assert calls == []

    def test_with_a_dsn_it_sends_errors_only_and_no_personal_data(self, monkeypatch):
        import sentry_sdk

        calls = []
        monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
        assert configure_error_tracking("https://key@o0.ingest.sentry.io/1", "staging") is True
        [options] = calls
        assert options["dsn"] == "https://key@o0.ingest.sentry.io/1"
        assert options["environment"] == "staging"
        assert options["send_default_pii"] is False
        assert options["max_request_body_size"] == "never"
        assert options["traces_sample_rate"] == 0

        token = observability._request_id.set("req-12345678")
        try:
            event = options["before_send"]({}, {})
        finally:
            observability._request_id.reset(token)
        assert event["tags"]["request_id"] == "req-12345678"
