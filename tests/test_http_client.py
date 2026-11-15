"""The shared outbound HTTP client: one for the whole app, opened at startup, closed at shutdown."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import http_client
from app.main import app


def test_one_client_opens_when_the_app_starts_and_closes_when_it_stops(monkeypatch):
    # This test is about the real client, so drop the stand-in the suite installs.
    monkeypatch.setattr(http_client, "_client", None)

    with TestClient(app):
        client = http_client.get_http_client()
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed
        assert http_client.get_http_client() is client
        assert client.timeout == httpx.Timeout(10)

    assert client.is_closed


def test_asking_for_the_client_before_it_is_open_is_an_error(monkeypatch):
    monkeypatch.setattr(http_client, "_client", None)

    with pytest.raises(RuntimeError, match="not open"):
        http_client.get_http_client()
