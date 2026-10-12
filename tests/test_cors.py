import pytest


def _preflight(client, origin):
    return client.options(
        "/api/v1/auth/login",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5273", "http://localhost:5175", "http://127.0.0.1:5173", "http://[::1]:5273"],
)
def test_local_dev_origins_are_allowed_on_any_port(client, origin):
    resp = _preflight(client, origin)
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", ["https://evil.example.com", "http://localhost.evil.com:5273"])
def test_other_origins_are_rejected(client, origin):
    assert _preflight(client, origin).status_code == 400
