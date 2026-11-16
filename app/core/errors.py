"""
The error a client can retry (ADR 0003): 503 with `{code, message, retryable}`.

Raised when a request can't be served right now and Demo data would be the
only way to answer: Google unreachable, no candidate places at all, the
database down. The web shows `message` with a Retry button. `detail` repeats
the message for clients that read FastAPI's usual field.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError

log = logging.getLogger(__name__)

RETRY_AFTER_SECONDS = 30


class ServiceUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def unavailable_response(code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": str(RETRY_AFTER_SECONDS)},
        content={"code": code, "message": message, "retryable": True, "detail": message},
    )


async def service_unavailable_handler(request: Request, exc: ServiceUnavailable) -> JSONResponse:
    log.warning("service unavailable", extra={"code": exc.code, "path": request.url.path})
    return unavailable_response(exc.code, exc.message)


async def database_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("database unavailable", extra={"path": request.url.path, "error": str(exc)[:200]})
    return unavailable_response("database_unavailable", "We can't reach our database right now. Please try again in a moment.")


def install_error_handlers(app) -> None:
    app.add_exception_handler(ServiceUnavailable, service_unavailable_handler)
    app.add_exception_handler(OperationalError, database_unavailable_handler)
    app.add_exception_handler(InterfaceError, database_unavailable_handler)
