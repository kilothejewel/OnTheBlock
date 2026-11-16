"""
Logging, request IDs, per-request call counts and error tracking.

- `configure_logging()` sends every log record to stdout, as one JSON object
  per line when OTB_LOG_FORMAT=json (Render), or readable text locally.
- `RequestContextMiddleware` gives every request an ID (the caller's
  `X-Request-ID` when it's a sane value, else a new one), puts it on every
  log line written while the request runs and on the response, and logs one
  line per request with its status, duration and outside calls.
- `count_call("google")` / `count_call("llm.gemini")` count calls to Google
  and LLM providers for the current request (`places._request` and the LLM
  client call it). `call_counts()` reads them.
- `configure_error_tracking()` turns Sentry on when OTB_SENTRY_DSN is set,
  and does nothing otherwise. Unhandled errors are reported with the
  request ID, and never with request bodies, cookies or user details.
"""

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Dict, Optional

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_calls: ContextVar[Optional[Dict[str, int]]] = ContextVar("calls", default=None)

log = logging.getLogger("app.request")

# LogRecord attributes that aren't "extra" fields.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}


def current_request_id() -> Optional[str]:
    return _request_id.get()


def count_call(provider: str, n: int = 1) -> None:
    """Count an outside call for the current request, e.g. "google" or "llm.openai"."""
    calls = _calls.get()
    if calls is not None:
        calls[provider] = calls.get(provider, 0) + n


def call_counts() -> Dict[str, int]:
    """The current request's outside calls by provider (a copy)."""
    return dict(_calls.get() or {})


def call_summary() -> Dict[str, object]:
    """Google calls in total and LLM calls by provider, for log lines."""
    calls = call_counts()
    return {
        "google_calls": sum(n for provider, n in calls.items() if provider.split(".")[0] == "google"),
        "llm_calls": {provider.split(".", 1)[1]: n for provider, n in calls.items() if provider.startswith("llm.")},
    }


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line: time, level, logger, message, request_id and any `extra` fields."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and key not in entry and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = {k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS and k != "request_id" and not k.startswith("_")}
        return f"{line} {json.dumps(extras, default=str)}" if extras else line


def configure_logging(fmt: str = "text", level: str = "INFO") -> None:
    """Send app and uvicorn logs to stdout, as JSON lines or text, each with the request ID."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(_TextFormatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    # One line per request comes from RequestContextMiddleware, and outside
    # calls are counted on it, so the per-call lines of these are noise.
    for name in ("uvicorn.access", "httpx", "httpx2", "httpcore", "httpcore2"):
        logging.getLogger(name).setLevel(logging.WARNING)


def configure_error_tracking(dsn: Optional[str], environment: str = "production") -> bool:
    """Start Sentry when a DSN is set. Returns whether it's on."""
    if not dsn:
        return False
    import sentry_sdk

    def tag_request_id(event, hint):
        request_id = current_request_id()
        if request_id:
            event.setdefault("tags", {})["request_id"] = request_id
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        send_default_pii=False,  # no IPs, cookies, headers or user details
        max_request_body_size="never",  # never send request bodies (chat messages)
        traces_sample_rate=0,  # errors only: the free plan's quota goes to them
        before_send=tag_request_id,
    )
    return True


def _report_to_tracker(exc: BaseException) -> None:
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - sentry-sdk is in requirements.txt
        return
    if sentry_sdk.is_initialized():
        sentry_sdk.capture_exception(exc)


class RequestContextMiddleware:
    """
    Outermost middleware: request ID in, request ID out, one log line per
    request. An unhandled error becomes a plain 500 that still carries the
    request ID, and is logged and sent to the error tracker.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.lower().encode(), b"").decode("latin-1")
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        id_token, calls_token = _request_id.set(request_id), _calls.set({})
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status = message["status"]
                response_started = True
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != REQUEST_ID_HEADER.lower().encode()]
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            log.exception("unhandled error", extra={"method": scope.get("method"), "path": scope.get("path")})
            _report_to_tracker(exc)
            if response_started:
                raise
            status = 500
            await JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)(scope, receive, send_with_id)
        finally:
            log.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    **call_summary(),
                },
            )
            _calls.reset(calls_token)
            _request_id.reset(id_token)
