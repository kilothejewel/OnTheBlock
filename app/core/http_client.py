"""
The one outbound HTTP client.

Opened when the app starts and closed when it stops (the lifespan in
app.main), so every call to Google, and later to the LLM providers, reuses
connections instead of paying a TCP and TLS handshake each time. Code that
runs outside the app (a script) opens and closes it itself.
"""

from typing import Optional

import httpx

TIMEOUT_SECONDS = 10

_client: Optional[httpx.AsyncClient] = None


def open_http_client() -> httpx.AsyncClient:
    """Create the shared client, or return the one that's already open."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=TIMEOUT_SECONDS)
    return _client


async def close_http_client() -> None:
    """Close the shared client and its connections. Does nothing when it isn't open."""
    global _client
    if _client is not None:
        client, _client = _client, None
        await client.aclose()


def get_http_client() -> httpx.AsyncClient:
    """The shared client. Use this for every outbound request; never create another client."""
    if _client is None:
        raise RuntimeError(
            "The HTTP client is not open. The app opens it at startup; "
            "outside the app, call open_http_client() first."
        )
    return _client
