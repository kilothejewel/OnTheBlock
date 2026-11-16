"""
The LLM seam: the only module that talks to an LLM provider (ADR 0006).

    result = await llm.extract_brief(history, brief, country="ZA")
    result = await llm.compose_plan(skeleton, candidates, brief)

`llm` is an `LLMChain` that tries each provider in OTB_LLM_CHAIN (default
gemini, groq, rules) and moves to the next on a 429, a 5xx (after one retry),
a timeout, a refusal, output that fails validation after one repair attempt,
a missing key, a blocked region, or the free-quota guard (#121) saying the
model's allowance is used. `RulesLLMClient` needs no model and never fails,
so a Plan always comes back, and never from Demo data (ADR 0003, #42).

Free-tier rules: providers may use these prompts and people may read them.
Only chat text, the Brief and place data are sent, never a user id, email,
name, phone number or exact location, and `redact` strips emails and phone
numbers from user text first. Gemini isn't used for the EEA, the UK or
Switzerland (unpaid Gemini can't serve them), nor for London Plans.

Providers are called over REST with the shared HTTP client: no provider SDK.
Every result carries provider, model, tokens, latency and the fallbacks tried.
"""

import asyncio
import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.http_client import get_http_client
from app.core.observability import count_call
from app.schemas.llm import (
    Candidate, ComposedStop, ComposeResult, IntakePatch, IntakeResult, LLMMeta, SkeletonSlot, Turn,
)
from app.services.interests import INTERESTS, match_interests
from app.services.quota import quota as default_quota

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


# --------------------------------------------------------------------------
# Redaction and region
# --------------------------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# SA numbers (082 123 4567, 0821234567, +27 82 123 4567, 27821234567) and
# other international numbers of 9+ digits, with spaces, dots or dashes.
_PHONE = re.compile(r"(?<![\w])(?:\+?\d{1,3}[\s.-]?)?(?:\(?0?\d{2,3}\)?[\s.-]?)\d{3}[\s.-]?\d{3,4}(?![\w])")


def redact(text: str) -> str:
    """User text with emails and phone numbers replaced, before any provider sees it."""
    text = _EMAIL.sub("[email removed]", text or "")
    return _PHONE.sub(lambda m: "[phone removed]" if len(re.sub(r"\D", "", m.group())) >= 9 else m.group(), text)


def gemini_blocked(country: Optional[str], brief: Optional[Dict[str, Any]]) -> bool:
    """Whether Gemini's free tier may not be used: a blocked request country, or a London Plan."""
    blocked = {c.strip().upper() for c in settings.GEMINI_BLOCKED_COUNTRIES.split(",") if c.strip()}
    if country and country.upper() in blocked:
        return True
    return (brief or {}).get("city") == "london"


def request_country(headers: Dict[str, str]) -> Optional[str]:
    """The visitor's country from a host's geo header, when the host sends one."""
    for name in ("cf-ipcountry", "x-vercel-ip-country", "x-country-code"):
        value = {k.lower(): v for k, v in headers.items()}.get(name)
        if value and re.fullmatch(r"[A-Za-z]{2}", value):
            return value.upper()
    return None


# --------------------------------------------------------------------------
# Prompts and schemas
# --------------------------------------------------------------------------

INTAKE_SYSTEM = (
    "You help plan a day or night out in a South African city. From the chat, extract what the "
    "user wants for their Plan and decide the next action. Only use interests from the allowed list. "
    "Budgets are in South African rand: 'R1,000', '1k' and 'a grand' are 1000. Use null for anything "
    "not mentioned. next_action is 'plan' when there's enough to plan (at least one interest or a "
    "clear mode), 'ask' with one short question otherwise, and 'off_topic' when the message isn't "
    "about planning an outing. Never invent places, prices or times."
)

COMPOSE_SYSTEM = (
    "You write a short Plan for a day or night out. For each Slot, pick exactly one candidate key "
    "from that Slot's list and write a title (the place's name) and one or two friendly sentences. "
    "Don't mention prices, opening hours or times: those come from elsewhere. Don't invent facts "
    "beyond the candidate details. Write a one-sentence intro for the whole Plan."
)


def _nullable(schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def intake_schema() -> Dict[str, Any]:
    """Strict JSON schema: every field required, nulls for "not mentioned" (Groq strict mode needs this)."""
    return {
        "type": "object",
        "properties": {
            "interests": {"type": "array", "items": {"type": "string", "enum": sorted(INTERESTS)}},
            "budget_zar": _nullable({"type": "integer"}),
            "date": _nullable({"type": "string", "description": "YYYY-MM-DD"}),
            "mode": _nullable({"type": "string", "enum": ["day_out", "night_out"]}),
            "area": _nullable({"type": "string"}),
            "group_size": _nullable({"type": "integer"}),
            "next_action": {"type": "string", "enum": ["ask", "plan", "off_topic"]},
            "question": _nullable({"type": "string"}),
        },
        "required": ["interests", "budget_zar", "date", "mode", "area", "group_size", "next_action", "question"],
        "additionalProperties": False,
    }


def compose_schema(skeleton: Sequence[SkeletonSlot], candidates: Dict[str, Sequence[Candidate]]) -> Dict[str, Any]:
    """One object per Slot whose candidate_key is an enum of that Slot's keys: the LLM can't pick anything else."""
    slots = {}
    for slot in skeleton:
        slots[slot.slot_id] = {
            "type": "object",
            "properties": {
                "candidate_key": {"type": "string", "enum": [c.key for c in candidates.get(slot.slot_id, [])]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["candidate_key", "title", "description"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "intro": {"type": "string"},
            "stops": {"type": "object", "properties": slots, "required": list(slots), "additionalProperties": False},
        },
        "required": ["intro", "stops"],
        "additionalProperties": False,
    }


def _intake_prompt(history: Sequence[Turn], brief: Dict[str, Any]) -> str:
    lines = [f"{turn.role}: {redact(turn.text)}" for turn in history[-12:]]
    return (
        f"Allowed interests: {', '.join(sorted(INTERESTS))}\n"
        f"What we know so far: {json.dumps(_safe_brief(brief), ensure_ascii=False)}\n"
        "Chat:\n" + "\n".join(lines)
    )


def _compose_prompt(skeleton: Sequence[SkeletonSlot], candidates: Dict[str, Sequence[Candidate]], brief: Dict[str, Any]) -> str:
    payload = {
        "brief": _safe_brief(brief),
        "slots": [
            {
                "slot_id": slot.slot_id, "kind": slot.kind, "start": slot.start, "interest": slot.interest,
                "candidates": [c.model_dump(exclude={"score"}) for c in candidates.get(slot.slot_id, [])],
            }
            for slot in skeleton
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


# The Brief fields a provider may see: no user or account details, no exact location.
_BRIEF_FIELDS = ("city", "date", "mode", "area", "interests", "budget_zar", "group_size")


def _safe_brief(brief: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    safe = {k: v for k, v in (brief or {}).items() if k in _BRIEF_FIELDS and v is not None}
    if isinstance(safe.get("area"), str):
        safe["area"] = redact(safe["area"])
    return safe


def _parse_intake(data: Dict[str, Any], meta: LLMMeta) -> IntakeResult:
    patch = IntakePatch.model_validate({k: data.get(k) for k in ("budget_zar", "date", "mode", "area", "group_size")} | {
        "interests": [i for i in (data.get("interests") or []) if i in INTERESTS],
    })
    action = data.get("next_action")
    question = data.get("question")
    if action == "ask" and not question:
        raise ValueError("next_action is 'ask' but there's no question")
    return IntakeResult(patch=patch, next_action=action, question=question, meta=meta)


def _parse_compose(data: Dict[str, Any], skeleton, candidates, meta: LLMMeta) -> ComposeResult:
    """Validate the output again in code, whatever the provider promises."""
    stops_in = data.get("stops") or {}
    stops = []
    for slot in skeleton:
        raw = stops_in.get(slot.slot_id)
        if not isinstance(raw, dict):
            raise ValueError(f"no stop for {slot.slot_id}")
        allowed = {c.key for c in candidates.get(slot.slot_id, [])}
        if raw.get("candidate_key") not in allowed:
            raise ValueError(f"{slot.slot_id}: {raw.get('candidate_key')!r} isn't one of its candidates")
        stops.append(ComposedStop(slot_id=slot.slot_id, candidate_key=raw["candidate_key"], title=raw.get("title", ""), description=raw.get("description", "")))
    return ComposeResult(intro=data.get("intro") or "", stops=stops, meta=meta)


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------

class ProviderError(Exception):
    """A provider couldn't answer; `reason` says why, for the fallbacks list."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class LLMClient(Protocol):
    name: str

    async def extract_brief(self, history: Sequence[Turn], brief: Dict[str, Any], **kwargs) -> IntakeResult: ...

    async def compose_plan(self, skeleton: Sequence[SkeletonSlot], candidates: Dict[str, Sequence[Candidate]], brief: Dict[str, Any], **kwargs) -> ComposeResult: ...


class _HttpProvider:
    """Shared request handling: timeout, one jittered retry on 5xx, errors as ProviderError."""

    name = "provider"

    async def _post(self, url: str, headers: Dict[str, str], body: Dict[str, Any]) -> Dict[str, Any]:
        for attempt in (1, 2):
            try:
                count_call(f"llm.{self.name}")
                response = await get_http_client().post(url, headers=headers, json=body, timeout=settings.LLM_TIMEOUT_SECONDS)
            except httpx.TimeoutException as exc:
                raise ProviderError("timeout", str(exc))
            except httpx.HTTPError as exc:
                raise ProviderError("unreachable", str(exc))
            if response.status_code == 429:
                raise ProviderError("rate_limited")
            if response.status_code >= 500:
                if attempt == 1:
                    await asyncio.sleep(random.uniform(0.2, 0.8))
                    continue
                raise ProviderError("server_error", str(response.status_code))
            if response.status_code != 200:
                raise ProviderError("refused", f"{response.status_code} {response.text[:200]}")
            try:
                return response.json()
            except ValueError:
                raise ProviderError("invalid_output", "response isn't JSON")
        raise ProviderError("server_error")  # pragma: no cover

    async def _structured(self, model: str, system: str, prompt: str, schema: Dict[str, Any], name: str) -> Tuple[Dict[str, Any], int, int]:
        raise NotImplementedError

    async def _call(self, task: str, model: str, system: str, prompt: str, schema, parse):
        """One call with one repair attempt when the output doesn't validate."""
        started = time.perf_counter()
        tokens_in = tokens_out = 0
        attempt_prompt = prompt
        for attempt in (1, 2):
            data, t_in, t_out = await self._structured(model, system, attempt_prompt, schema, task)
            tokens_in, tokens_out = tokens_in + t_in, tokens_out + t_out
            meta = LLMMeta(provider=self.name, model=model, input_tokens=tokens_in, output_tokens=tokens_out,
                           latency_ms=round((time.perf_counter() - started) * 1000, 1))
            try:
                return parse(data, meta)
            except (ValueError, ValidationError, TypeError, KeyError) as exc:
                if attempt == 2:
                    raise ProviderError("invalid_output", str(exc)[:200])
                attempt_prompt = f"{prompt}\n\nYour last answer was invalid ({str(exc)[:200]}). Answer again, following the schema exactly."
        raise ProviderError("invalid_output")  # pragma: no cover

    def intake_model(self) -> str: ...

    def compose_model(self) -> str: ...

    async def extract_brief(self, history, brief, **kwargs) -> IntakeResult:
        return await self._call("intake", self.intake_model(), INTAKE_SYSTEM, _intake_prompt(history, brief), intake_schema(), _parse_intake)

    async def compose_plan(self, skeleton, candidates, brief, **kwargs) -> ComposeResult:
        return await self._call(
            "compose", self.compose_model(), COMPOSE_SYSTEM, _compose_prompt(skeleton, candidates, brief),
            compose_schema(skeleton, candidates), lambda data, meta: _parse_compose(data, skeleton, candidates, meta),
        )


class GeminiLLMClient(_HttpProvider):
    """Gemini API free tier through the Interactions API, with JSON schema output (store=false)."""

    name = "gemini"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY

    def intake_model(self) -> str:
        return settings.GEMINI_INTAKE_MODEL

    def compose_model(self) -> str:
        return settings.GEMINI_COMPOSE_MODEL

    async def _structured(self, model, system, prompt, schema, name):
        body = {
            "model": model,
            "system_instruction": system,
            "input": prompt,
            "response_format": {"type": "text", "mime_type": "application/json", "schema": schema},
            "generation_config": {"temperature": 0.4},
            "store": False,  # the free tier would otherwise keep the prompt for a day
        }
        headers = {"x-goog-api-key": self.api_key, "Api-Revision": settings.GEMINI_API_REVISION}
        data = await self._post(GEMINI_URL, headers, body)
        texts = [
            part.get("text", "")
            for step in data.get("steps") or []
            if step.get("type") == "model_output"
            for part in step.get("content") or []
            if part.get("type") == "text"
        ]
        if not texts or not "".join(texts).strip():
            raise ProviderError("refused", "no output text")
        usage = data.get("usage") or {}
        try:
            parsed = json.loads("".join(texts))
        except ValueError:
            parsed = {"_unparsed": "".join(texts)}
        return parsed, int(usage.get("total_input_tokens", 0)), int(usage.get("total_output_tokens", 0))


class GroqLLMClient(_HttpProvider):
    """Groq free plan, OpenAI-compatible chat completions with strict JSON schema output."""

    name = "groq"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY

    def intake_model(self) -> str:
        return settings.GROQ_INTAKE_MODEL

    def compose_model(self) -> str:
        return settings.GROQ_COMPOSE_MODEL

    async def _structured(self, model, system, prompt, schema, name):
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}},
            "temperature": 0.4,
        }
        data = await self._post(GROQ_URL, {"Authorization": f"Bearer {self.api_key}"}, body)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("invalid_output", "no choices")
        if message.get("refusal"):
            raise ProviderError("refused", str(message["refusal"])[:200])
        content = message.get("content") or ""
        if not content.strip():
            raise ProviderError("refused", "empty content")
        usage = data.get("usage") or {}
        try:
            parsed = json.loads(content)
        except ValueError:
            parsed = {"_unparsed": content}
        return parsed, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


# --------------------------------------------------------------------------
# Rules: no model, never fails
# --------------------------------------------------------------------------

_AMOUNT = re.compile(r"(?i)\b(?:r\s?(\d{1,3}(?:[ ,]\d{3})+|\d+)(k)?|(\d{1,3}(?:[ ,]\d{3})+|\d+)\s?(k)\b|(\d+)\s?(?:rand|zar)\b)")
_GRAND = re.compile(r"(?i)\b(a|one|two|three|four|five)\s+grand\b")
_WORDS = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def parse_budget_zar(text: str) -> Optional[int]:
    """A rand amount in chat text: "R1,000", "R1000", "R2k", "1k", "a grand", "500 rand". Bare numbers don't count."""
    text = text or ""
    grand = _GRAND.search(text)
    if grand:
        return _WORDS[grand.group(1).lower()] * 1000
    match = _AMOUNT.search(text)
    if not match:
        return None
    digits, k = (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4)) if match.group(3) else (match.group(5), None)
    amount = int(re.sub(r"[ ,]", "", digits))
    return amount * 1000 if k else amount


_NIGHT = re.compile(r"(?i)\b(tonight|night|evening|late|after dark|jol|clubbing|club)\b")
_DAY = re.compile(r"(?i)\b(morning|day out|daytime|afternoon|brunch|breakfast|lunch)\b")


class RulesLLMClient:
    """
    The planner with no model: intake from match_interests and money/mode
    rules (#91's quick path), compose from the top-scored candidate per Slot
    with template copy. Deterministic, so tests and keyless runs use it.
    """

    name = "rules"

    async def extract_brief(self, history: Sequence[Turn], brief: Dict[str, Any], **kwargs) -> IntakeResult:
        started = time.perf_counter()
        text = " ".join(redact(turn.text) for turn in history if turn.role == "user")
        latest = next((redact(t.text) for t in reversed(history) if t.role == "user"), "")
        interests = [key for key, _ in match_interests(latest)] or [key for key, _ in match_interests(text)]
        mode = "night_out" if _NIGHT.search(latest) else "day_out" if _DAY.search(latest) else None
        patch = IntakePatch(interests=interests, budget_zar=parse_budget_zar(latest), mode=mode)
        known = bool(interests or (brief or {}).get("interests") or mode or (brief or {}).get("mode"))
        meta = LLMMeta(provider=self.name, latency_ms=round((time.perf_counter() - started) * 1000, 1))
        if known:
            return IntakeResult(patch=patch, next_action="plan", meta=meta)
        return IntakeResult(
            patch=patch, next_action="ask",
            question="What are you in the mood for? For example a hike, the beach, wine farms, food or a night out.",
            meta=meta,
        )

    async def compose_plan(self, skeleton: Sequence[SkeletonSlot], candidates: Dict[str, Sequence[Candidate]], brief: Dict[str, Any], **kwargs) -> ComposeResult:
        started = time.perf_counter()
        stops = []
        for slot in skeleton:
            pool = list(candidates.get(slot.slot_id, []))
            if not pool:
                continue
            best = max(pool, key=lambda c: c.score)  # first of equal scores
            interest = INTERESTS.get(slot.interest or "")
            where = f" in {best.area}" if best.area else ""
            reason = best.snippet or (interest.description if interest else "")
            stops.append(ComposedStop(
                slot_id=slot.slot_id, candidate_key=best.key, title=best.name,
                description=(f"{best.name}{where}. {reason}".strip())[:600],
            ))
        city = (brief or {}).get("city", "").replace("-", " ").title()
        intro = f"Here's your Plan for {city}." if city else "Here's your Plan."
        meta = LLMMeta(provider=self.name, latency_ms=round((time.perf_counter() - started) * 1000, 1))
        return ComposeResult(intro=intro, stops=stops, meta=meta)


# --------------------------------------------------------------------------
# The chain
# --------------------------------------------------------------------------

class LLMChain:
    """Tries each provider in order; the rules client is always the last resort."""

    def __init__(self, providers: Optional[List[Any]] = None, quota=None):
        self.providers = providers if providers is not None else self._from_config()
        if not any(isinstance(p, RulesLLMClient) for p in self.providers):
            self.providers.append(RulesLLMClient())
        self.quota = quota if quota is not None else default_quota

    @staticmethod
    def _from_config() -> List[Any]:
        known = {"gemini": GeminiLLMClient, "groq": GroqLLMClient, "rules": RulesLLMClient}
        return [known[name.strip()]() for name in settings.LLM_CHAIN.split(",") if name.strip() in known]

    def _skip_reason(self, provider, model: str, country, brief, pool: str) -> Optional[str]:
        if isinstance(provider, RulesLLMClient):
            return None
        if not getattr(provider, "api_key", None):
            return "no_key"
        if provider.name == "gemini" and gemini_blocked(country, brief):
            return "region"
        try:
            allowed = self.quota.take(f"llm.{provider.name}.{model}", pool=pool)
        except Exception:  # can't tell if there's allowance left: don't spend it blind
            log.exception("quota check failed", extra={"provider": provider.name})
            return "quota_error"
        if not allowed:
            return "quota"
        return None

    async def _run(self, task: str, brief, country, pool, call):
        fallbacks: List[str] = []
        for provider in self.providers:
            model = None if isinstance(provider, RulesLLMClient) else (provider.intake_model() if task == "intake" else provider.compose_model())
            reason = self._skip_reason(provider, model, country, brief, pool)
            if reason:
                fallbacks.append(f"{provider.name}:{reason}")
                continue
            try:
                result = await call(provider)
            except ProviderError as exc:
                log.warning("llm provider failed", extra={"provider": provider.name, "task": task, "reason": exc.reason})
                fallbacks.append(f"{provider.name}:{exc.reason}")
                continue
            result.meta.fallbacks = fallbacks
            if fallbacks:
                log.info("llm fell back", extra={"task": task, "answered_by": provider.name, "fallbacks": fallbacks})
            return result
        raise RuntimeError("no LLM provider answered, not even the rules client")  # pragma: no cover

    async def extract_brief(self, history: Sequence[Turn], brief: Optional[Dict[str, Any]] = None, *, country: Optional[str] = None, pool: str = "users") -> IntakeResult:
        brief = brief or {}
        return await self._run("intake", brief, country, pool, lambda p: p.extract_brief(history, brief))

    async def compose_plan(self, skeleton: Sequence[SkeletonSlot], candidates: Dict[str, Sequence[Candidate]], brief: Optional[Dict[str, Any]] = None, *, country: Optional[str] = None, pool: str = "users") -> ComposeResult:
        brief = brief or {}
        return await self._run("compose", brief, country, pool, lambda p: p.compose_plan(skeleton, candidates, brief))


class FakeLLMClient:
    """For tests: replays canned results in order, or raises ProviderError for a reason string."""

    def __init__(self, name: str = "fake", intake: Sequence[Any] = (), compose: Sequence[Any] = ()):
        self.name = name
        self.api_key = "fake"
        self._intake, self._compose = list(intake), list(compose)
        self.calls: List[Tuple[str, Any]] = []

    def intake_model(self) -> str:
        return "fake-intake"

    def compose_model(self) -> str:
        return "fake-compose"

    @staticmethod
    def _next(queue, name):
        item = queue.pop(0)
        if isinstance(item, str):
            raise ProviderError(item)
        if isinstance(item, (IntakeResult, ComposeResult)):
            item.meta = LLMMeta(provider=name, model="fake")
        return item

    async def extract_brief(self, history, brief, **kwargs) -> IntakeResult:
        self.calls.append(("intake", history))
        return self._next(self._intake, self.name)

    async def compose_plan(self, skeleton, candidates, brief, **kwargs) -> ComposeResult:
        self.calls.append(("compose", skeleton))
        return self._next(self._compose, self.name)


llm = LLMChain()
