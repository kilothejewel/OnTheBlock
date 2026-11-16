"""The LLM seam (#90): providers over mocked HTTP, the fallback chain, redaction and region rules."""

import ast
import json
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.schemas.llm import Candidate, SkeletonSlot, Turn
from app.services import llm as llm_module
from app.services.llm import (
    FakeLLMClient, GeminiLLMClient, GroqLLMClient, LLMChain, RulesLLMClient, compose_schema, gemini_blocked,
    intake_schema, parse_budget_zar, redact, request_country,
)

HISTORY = [Turn(role="user", text="I love nature and want to go clubbing tonight, about R1,000")]
INTAKE_OUT = {
    "interests": ["nature", "clubbing"], "budget_zar": 1000, "date": None, "mode": "night_out",
    "area": None, "group_size": None, "next_action": "plan", "question": None,
}
SKELETON = [SkeletonSlot(slot_id="s1", kind="activity", start="16:00", interest="nature"),
            SkeletonSlot(slot_id="s2", kind="nightlife", start="22:00", interest="clubbing")]
CANDIDATES = {
    "s1": [Candidate(key="s1c1", name="Kirstenbosch", area="Newlands", score=0.9), Candidate(key="s1c2", name="Lion's Head", score=0.7)],
    "s2": [Candidate(key="s2c1", name="Club A", area="City Bowl", score=0.5), Candidate(key="s2c2", name="Club B", score=0.8)],
}
COMPOSE_OUT = {
    "intro": "A green afternoon, then dancing.",
    "stops": {
        "s1": {"candidate_key": "s1c2", "title": "Lion's Head", "description": "Hike up for sunset."},
        "s2": {"candidate_key": "s2c2", "title": "Club B", "description": "Amapiano till late."},
    },
}


class AllowAll:
    def __init__(self, refuse=()):
        self.refuse, self.taken = set(refuse), []

    def take(self, resource, n=1, pool="users"):
        self.taken.append((resource, pool))
        return not any(resource.startswith(prefix) for prefix in self.refuse)


def gemini_reply(payload, status=200):
    body = {"id": "int_1", "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(payload) if not isinstance(payload, str) else payload}]}],
            "usage": {"total_input_tokens": 120, "total_output_tokens": 40, "total_tokens": 160}}
    return httpx.Response(status, json=body)


def groq_reply(payload, status=200, refusal=None):
    body = {"choices": [{"message": {"role": "assistant", "content": json.dumps(payload) if payload is not None else None, "refusal": refusal}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 30}}
    return httpx.Response(status, json=body)


@pytest.fixture
def providers():
    return [GeminiLLMClient(api_key="gk"), GroqLLMClient(api_key="qk"), RulesLLMClient()]


@pytest.fixture
def route(outbound_http):
    """Answer Gemini and Groq from per-host queues of responses (or exceptions)."""
    queues = {"generativelanguage.googleapis.com": [], "api.groq.com": []}

    def handle(request):
        item = queues[request.url.host].pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    outbound_http.respond_with(handle)
    return queues


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def instant(_):
        return None
    monkeypatch.setattr(llm_module.asyncio, "sleep", instant)


async def intake(providers, quota=None, **kw):
    return await LLMChain(providers, quota=quota or AllowAll()).extract_brief(HISTORY, {"city": "cape-town"}, **kw)


class TestProviders:
    async def test_gemini_success(self, providers, route, outbound_http):
        route["generativelanguage.googleapis.com"].append(gemini_reply(INTAKE_OUT))
        result = await intake(providers)

        assert result.patch.interests == ["nature", "clubbing"] and result.patch.budget_zar == 1000
        assert (result.next_action, result.meta.provider, result.meta.model) == ("plan", "gemini", settings.GEMINI_INTAKE_MODEL)
        assert (result.meta.input_tokens, result.meta.output_tokens, result.meta.fallbacks) == (120, 40, [])

        [request] = outbound_http.requests
        body = json.loads(request.content)
        assert request.url.path == "/v1beta/interactions"
        assert request.headers["x-goog-api-key"] == "gk"
        assert request.headers["Api-Revision"] == settings.GEMINI_API_REVISION
        assert body["store"] is False
        assert body["response_format"]["mime_type"] == "application/json"
        assert body["response_format"]["schema"] == intake_schema()

    async def test_groq_success_with_strict_schema(self, route, outbound_http):
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        result = await intake([GroqLLMClient(api_key="qk")])

        assert result.meta.provider == "groq"
        body = json.loads(outbound_http.requests[0].content)
        assert outbound_http.requests[0].headers["Authorization"] == "Bearer qk"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["model"] == settings.GROQ_INTAKE_MODEL

    async def test_compose_picks_only_offered_candidates(self, providers, route):
        route["generativelanguage.googleapis.com"].append(gemini_reply(COMPOSE_OUT))
        result = await LLMChain(providers, quota=AllowAll()).compose_plan(SKELETON, CANDIDATES, {"city": "cape-town"})
        assert [(s.slot_id, s.candidate_key) for s in result.stops] == [("s1", "s1c2"), ("s2", "s2c2")]
        assert result.meta.provider == "gemini"

    def test_the_compose_schema_is_an_enum_of_each_slots_keys(self):
        schema = compose_schema(SKELETON, CANDIDATES)
        stops = schema["properties"]["stops"]
        assert stops["required"] == ["s1", "s2"]
        assert stops["properties"]["s1"]["properties"]["candidate_key"]["enum"] == ["s1c1", "s1c2"]
        assert stops["additionalProperties"] is False


class TestFallbacks:
    async def test_429_moves_to_the_next_provider(self, providers, route):
        route["generativelanguage.googleapis.com"].append(httpx.Response(429, json={}))
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        result = await intake(providers)
        assert (result.meta.provider, result.meta.fallbacks) == ("groq", ["gemini:rate_limited"])

    async def test_5xx_is_retried_once_then_falls_back(self, providers, route, outbound_http):
        route["generativelanguage.googleapis.com"] += [httpx.Response(503), httpx.Response(500)]
        route["api.groq.com"] += [httpx.Response(502), groq_reply(INTAKE_OUT)]
        result = await intake(providers)
        assert (result.meta.provider, result.meta.fallbacks) == ("groq", ["gemini:server_error"])
        assert len(outbound_http.requests) == 4

    async def test_timeout_falls_back(self, providers, route):
        route["generativelanguage.googleapis.com"].append(httpx.ReadTimeout("slow"))
        route["api.groq.com"].append(httpx.ConnectTimeout("slow"))
        result = await intake(providers)
        assert (result.meta.provider, result.meta.fallbacks) == ("rules", ["gemini:timeout", "groq:timeout"])

    async def test_refusal_falls_back(self, providers, route):
        route["generativelanguage.googleapis.com"].append(httpx.Response(200, json={"steps": []}))
        route["api.groq.com"].append(groq_reply(None, refusal="I can't help with that."))
        result = await intake(providers)
        assert result.meta.fallbacks == ["gemini:refused", "groq:refused"]

    async def test_invalid_output_gets_one_repair_try(self, providers, route, outbound_http):
        bad = {**INTAKE_OUT, "next_action": "ask", "question": None}
        route["generativelanguage.googleapis.com"] += [gemini_reply("not json at all"), gemini_reply(INTAKE_OUT)]
        result = await intake(providers)
        assert result.meta.provider == "gemini" and result.meta.input_tokens == 240
        assert "was invalid" in json.loads(outbound_http.requests[1].content)["input"]

        route["generativelanguage.googleapis.com"] += [gemini_reply(bad), gemini_reply(bad)]
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        result = await intake(providers)
        assert result.meta.fallbacks == ["gemini:invalid_output"]

    async def test_a_composed_key_that_wasnt_offered_is_invalid_output(self, providers, route):
        made_up = {**COMPOSE_OUT, "stops": {**COMPOSE_OUT["stops"], "s2": {"candidate_key": "s9c9", "title": "x", "description": "y"}}}
        route["generativelanguage.googleapis.com"] += [gemini_reply(made_up), gemini_reply(made_up)]
        route["api.groq.com"] += [groq_reply(made_up), groq_reply(made_up)]
        result = await LLMChain(providers, quota=AllowAll()).compose_plan(SKELETON, CANDIDATES, {})
        assert result.meta.provider == "rules"
        assert [s.candidate_key for s in result.stops] == ["s1c1", "s2c2"]  # top score per Slot

    async def test_all_models_down_the_rules_client_answers(self, providers, route):
        route["generativelanguage.googleapis.com"].append(httpx.ConnectError("down"))
        route["api.groq.com"].append(httpx.ConnectError("down"))
        result = await intake(providers)
        assert result.meta.provider == "rules"
        assert result.patch.interests == ["nature", "clubbing"] and result.patch.budget_zar == 1000
        assert result.patch.mode == "night_out" and result.next_action == "plan"

    async def test_quota_refused_skips_the_model_without_calling_it(self, providers, route, outbound_http):
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        quota = AllowAll(refuse=["llm.gemini."])
        result = await intake(providers, quota=quota, pool="guests")
        assert result.meta.fallbacks == ["gemini:quota"]
        assert [r.url.host for r in outbound_http.requests] == ["api.groq.com"]
        assert quota.taken == [(f"llm.gemini.{settings.GEMINI_INTAKE_MODEL}", "guests"), (f"llm.groq.{settings.GROQ_INTAKE_MODEL}", "guests")]

    async def test_a_broken_quota_check_never_spends_blind(self, providers, outbound_http):
        class Broken:
            def take(self, *a, **k):
                raise RuntimeError("database down")
        result = await intake(providers, quota=Broken())
        assert result.meta.fallbacks == ["gemini:quota_error", "groq:quota_error"]
        assert outbound_http.requests == []

    async def test_providers_without_a_key_are_skipped(self, outbound_http):
        result = await intake([GeminiLLMClient(api_key=""), GroqLLMClient(api_key=None)])
        assert result.meta.fallbacks == ["gemini:no_key", "groq:no_key"]
        assert outbound_http.requests == []

    async def test_the_rules_client_is_always_last(self):
        assert isinstance(LLMChain([GeminiLLMClient(api_key="k")], quota=AllowAll()).providers[-1], RulesLLMClient)


class TestPrivacy:
    @pytest.mark.parametrize("text", [
        "email me at thandi.m@example.co.za", "call 082 123 4567", "or +27 82 123 4567", "0821234567",
        "my number is 27821234567", "021-555-1234",
    ])
    def test_redact_removes_emails_and_phone_numbers(self, text):
        out = redact(text)
        assert "@" not in out and not any(ch.isdigit() for ch in out.replace("[", ""))

    def test_redact_keeps_amounts_times_and_dates(self):
        assert redact("R1,000 for 2 people at 19:30 on 2026-12-05") == "R1,000 for 2 people at 19:30 on 2026-12-05"

    async def test_an_email_and_an_sa_phone_number_never_reach_a_provider(self, providers, route, outbound_http):
        history = [Turn(role="user", text="Plan a wine day for me, thandi@example.com, 082 555 0199 or +27 82 555 0199")]
        route["generativelanguage.googleapis.com"] += [httpx.Response(429), ]
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        await LLMChain(providers, quota=AllowAll()).extract_brief(history, {"city": "stellenbosch", "user_id": 7, "email": "thandi@example.com", "area": "call 082 555 0199"})
        sent = " ".join(r.content.decode() for r in outbound_http.requests)
        for secret in ("thandi@example.com", "082 555 0199", "+27 82 555 0199", "0825550199", "user_id"):
            assert secret not in sent
        assert "wine day" in sent

    def test_no_module_outside_llm_imports_a_provider_sdk(self):
        app = Path(__file__).resolve().parents[1] / "app"
        sdks = ("google.genai", "google.generativeai", "groq", "openai", "anthropic")
        offenders = []
        for path in app.rglob("*.py"):
            if path.name == "llm.py":
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                for name in names:
                    if name.split(".")[0] in {s.split(".")[0] for s in sdks} and (name.startswith(sdks)):
                        offenders.append(f"{path.relative_to(app)}: {name}")
        # The v1 planner keeps openai until #118 removes it.
        assert offenders == ["services\\itinerary.py: openai"] or offenders == ["services/itinerary.py: openai"]


class TestRegion:
    @pytest.mark.parametrize("country", ["GB", "de", "FR", "CH", "NO"])
    async def test_a_blocked_country_skips_gemini(self, providers, route, outbound_http, country):
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        result = await intake(providers, country=country)
        assert result.meta.fallbacks == ["gemini:region"]
        assert all(r.url.host != "generativelanguage.googleapis.com" for r in outbound_http.requests)

    async def test_a_london_plan_skips_gemini(self, providers, route):
        route["api.groq.com"].append(groq_reply(INTAKE_OUT))
        result = await LLMChain(providers, quota=AllowAll()).extract_brief(HISTORY, {"city": "london"}, country="ZA")
        assert result.meta.fallbacks == ["gemini:region"]

    def test_south_africa_may_use_gemini(self):
        assert not gemini_blocked("ZA", {"city": "cape-town"})
        assert not gemini_blocked(None, {"city": "durban"})

    def test_request_country_reads_host_geo_headers(self):
        assert request_country({"CF-IPCountry": "za"}) == "ZA"
        assert request_country({"X-Vercel-IP-Country": "GB"}) == "GB"
        assert request_country({"CF-IPCountry": "XX1"}) is None
        assert request_country({}) is None


class TestRules:
    @pytest.mark.parametrize("text, amount", [
        ("about R1,000", 1000), ("R1000 max", 1000), ("R 500", 500), ("1k", 1000), ("R2k for two", 2000),
        ("a grand", 1000), ("two grand", 2000), ("500 rand", 500), ("R1 500", 1500),
        ("for 2 people", None), ("at 19:30", None), ("", None),
    ])
    def test_sa_money_formats(self, text, amount):
        assert parse_budget_zar(text) == amount

    async def test_intake_asks_when_it_knows_nothing(self):
        result = await RulesLLMClient().extract_brief([Turn(role="user", text="hello")], {})
        assert result.next_action == "ask" and result.question

    async def test_compose_writes_template_copy_from_the_top_candidate(self):
        result = await RulesLLMClient().compose_plan(SKELETON, CANDIDATES, {"city": "cape-town"})
        assert result.intro == "Here's your Plan for Cape Town."
        assert result.stops[0].title == "Kirstenbosch" and "Newlands" in result.stops[0].description


async def test_the_fake_client_replays_results_and_failures():
    fake = FakeLLMClient(intake=["rate_limited", await RulesLLMClient().extract_brief(HISTORY, {})])
    result = await LLMChain([fake, FakeLLMClient("second", intake=["timeout"])], quota=AllowAll()).extract_brief(HISTORY)
    assert result.meta.provider == "rules"
    assert result.meta.fallbacks == ["fake:rate_limited", "second:timeout"]
    result = await LLMChain([fake], quota=AllowAll()).extract_brief(HISTORY)
    assert result.meta.provider == "fake"
