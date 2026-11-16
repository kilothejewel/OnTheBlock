from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.security import user_id_from_token


def user_or_ip(request: Request) -> str:
    """
    Who a request counts against: the signed-in user (from a valid bearer
    token), else the client IP. Many phones share one carrier IP, so
    signed-in users each get their own limits.
    """
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        user_id = user_id_from_token(auth[7:].strip())
        if user_id is not None:
            return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


# A generous default limit protects every endpoint from abuse; expensive routes
# opt into stricter per-route limits via the @limiter.limit(...) decorator.
# Both are per user when signed in, per IP otherwise (user_or_ip).
limiter = Limiter(
    key_func=user_or_ip,
    default_limits=["100/minute"],
    headers_enabled=True,  # emit X-RateLimit-* and Retry-After headers
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clear JSON 429 body (plus the standard rate-limit headers)."""
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": (
                "Rate limit exceeded. You have sent too many requests; "
                f"the limit for this endpoint is {exc.detail}. "
                "Please wait a moment and try again."
            )
        },
    )
    # Attach X-RateLimit-* / Retry-After headers the same way slowapi's default handler does.
    return request.app.state.limiter._inject_headers(
        response, request.state.view_rate_limit
    )
