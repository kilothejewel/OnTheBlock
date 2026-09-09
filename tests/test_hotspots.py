HOTSPOT = {
    "google_place_id": "gpid_123",
    "name": "The Corner Spot",
    "rating": 4.6,
    "address": "10 Main St",
    "price_level": 2,
    "types": "cafe, restaurant",
}


def test_save_hotspot(client, auth_headers):
    resp = client.post("/api/v1/hotspots/", json=HOTSPOT, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["google_place_id"] == "gpid_123"
    assert body["id"]


def test_list_hotspots(client, auth_headers):
    client.post("/api/v1/hotspots/", json=HOTSPOT, headers=auth_headers)

    resp = client.get("/api/v1/hotspots/", headers=auth_headers)
    assert resp.status_code == 200
    names = [h["name"] for h in resp.json()]
    assert names == ["The Corner Spot"]


def test_delete_hotspot(client, auth_headers):
    client.post("/api/v1/hotspots/", json=HOTSPOT, headers=auth_headers)

    deleted = client.delete(
        f"/api/v1/hotspots/{HOTSPOT['google_place_id']}", headers=auth_headers
    )
    assert deleted.status_code == 204

    remaining = client.get("/api/v1/hotspots/", headers=auth_headers).json()
    assert remaining == []


def test_unauthorized_access_is_rejected(client):
    assert client.get("/api/v1/hotspots/").status_code == 401
    assert client.post("/api/v1/hotspots/", json=HOTSPOT).status_code == 401
    assert client.delete("/api/v1/hotspots/gpid_123").status_code == 401


def test_saved_hotspots_are_per_user(client, auth_headers):
    client.post("/api/v1/hotspots/", json=HOTSPOT, headers=auth_headers)

    other = client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "username": "bob", "password": "supersecret123"},
    ).json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other}"}

    assert client.get("/api/v1/hotspots/", headers=other_headers).json() == []
