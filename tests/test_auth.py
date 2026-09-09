def _register(client, **overrides):
    payload = {
        "email": "alice@example.com",
        "username": "alice",
        "password": "supersecret123",
    }
    payload.update(overrides)
    return client.post("/api/v1/auth/register", json=payload)


def test_register_success_returns_token(client):
    resp = _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_duplicate_registration_fails(client):
    assert _register(client).status_code == 201

    same_email = _register(client, username="alice2")
    assert same_email.status_code == 409
    assert "email" in same_email.json()["detail"]

    same_username = _register(client, email="other@example.com")
    assert same_username.status_code == 409
    assert "username" in same_username.json()["detail"]


def test_login_success(client):
    _register(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice", "password": "supersecret123"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    # login by email works too
    by_email = client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice@example.com", "password": "supersecret123"},
    )
    assert by_email.status_code == 200


def test_login_wrong_password_fails(client):
    _register(client)
    resp = client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_requires_valid_token(client):
    _register(client)

    # no token
    assert client.get("/api/v1/auth/me").status_code == 401

    # garbage / old-style mock token
    assert client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer mock_token_1"}
    ).status_code == 401

    # valid token
    token = client.post(
        "/api/v1/auth/login",
        json={"identifier": "alice", "password": "supersecret123"},
    ).json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "password" not in body and "hashed_password" not in body
