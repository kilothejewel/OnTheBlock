"""Guest sessions (#125): use the app without an account, keep the work on sign-up."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.security import create_guest_token, token_claims
from app.models.chat import Chat, ChatMessage
from app.models.user import User
from app.services import guests

PLAN = {"city": "cape-town", "budget": "$$", "duration_days": 1}
ACCOUNT = {"email": "thandi@example.com", "username": "thandi", "password": "supersecret123"}


def new_guest(client):
    resp = client.post("/api/v1/auth/guest")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}


def start_chat(db_session, user_id, text_="A hike and a jol"):
    chat = Chat(user_id=user_id, city="cape-town")
    chat.messages.append(ChatMessage(role="user", content=text_))
    db_session.add(chat)
    db_session.commit()
    return chat.id


def guest_id(headers):
    return int(token_claims(headers["Authorization"].split()[1])["sub"])


class TestSessions:
    def test_a_new_visitor_gets_a_guest_session_with_no_personal_data(self, client, db_session):
        body, headers = new_guest(client)
        assert body["is_guest"] is True
        claims = token_claims(body["access_token"])
        assert claims["typ"] == "guest"
        assert timedelta(days=29) < datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(timezone.utc) <= timedelta(days=30)

        me = client.get("/api/v1/auth/me", headers=headers).json()
        assert me["is_guest"] is True and me["email"] is None and me["username"] is None

        # and can start a chat (the chat API is #100; the chat belongs to the guest)
        chat_id = start_chat(db_session, me["id"])
        assert db_session.get(Chat, chat_id).user_id == me["id"]

    def test_guests_can_plan_and_see_place_details(self, client):
        _, headers = new_guest(client)
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=headers).status_code == 200
        assert client.get("/api/v1/places?ids=mock_cape-town_1", headers=headers).status_code == 200

    @pytest.mark.parametrize("method, path", [
        ("GET", "/api/v1/itineraries/"), ("POST", "/api/v1/itineraries/"), ("GET", "/api/v1/hotspots/"),
        ("POST", "/api/v1/hotspots/"), ("DELETE", "/api/v1/itineraries/1"),
    ])
    def test_a_guest_token_on_trips_or_saved_places_gets_account_required(self, client, method, path):
        _, headers = new_guest(client)
        resp = client.request(method, path, headers=headers, json={})
        assert resp.status_code == 401
        assert resp.json()["code"] == "account_required"
        assert resp.json()["message"] == "Create a free account to save this."

    def test_the_4th_guest_session_from_one_ip_in_a_day_is_429(self, client):
        for _ in range(3):
            new_guest(client)
        resp = client.post("/api/v1/auth/guest")
        assert resp.status_code == 429
        assert "Create a free account" in resp.json()["detail"]

    def test_turnstile_is_checked_when_configured(self, client, monkeypatch, outbound_http):
        import httpx
        monkeypatch.setattr(settings, "TURNSTILE_SECRET", "turnstile-secret")
        outbound_http.respond_with(lambda r: httpx.Response(200, json={"success": "real-token" in r.content.decode()}))
        assert client.post("/api/v1/auth/guest", json={}).status_code == 403
        assert client.post("/api/v1/auth/guest", json={"turnstile_token": "bad"}).status_code == 403
        assert client.post("/api/v1/auth/guest", json={"turnstile_token": "real-token"}).status_code == 201


class TestClaiming:
    def test_register_with_a_guest_token_keeps_the_same_user_id_and_chats(self, client, db_session):
        _, headers = new_guest(client)
        gid = guest_id(headers)
        start_chat(db_session, gid)

        resp = client.post("/api/v1/auth/register", json=ACCOUNT, headers=headers)

        assert resp.status_code == 201, resp.text
        assert resp.json()["claimed_chats"] == 1 and resp.json()["is_guest"] is False
        account_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        me = client.get("/api/v1/auth/me", headers=account_headers).json()
        assert (me["id"], me["is_guest"], me["username"]) == (gid, False, "thandi")
        db_session.expire_all()
        assert db_session.query(Chat).filter_by(user_id=gid).count() == 1

    def test_login_with_a_guest_token_moves_the_chats_and_deletes_the_guest(self, client, db_session):
        account_id = client.post("/api/v1/auth/register", json=ACCOUNT).json() and db_session.query(User).filter_by(username="thandi").one().id
        _, headers = new_guest(client)
        gid = guest_id(headers)
        start_chat(db_session, gid, "first")
        start_chat(db_session, gid, "second")

        resp = client.post("/api/v1/auth/login", json={"identifier": "thandi", "password": "supersecret123"}, headers=headers)

        assert resp.status_code == 200, resp.text
        assert resp.json()["claimed_chats"] == 2
        db_session.expire_all()
        assert db_session.get(User, gid) is None
        assert db_session.query(Chat).filter_by(user_id=account_id).count() == 2

    def test_logging_in_adds_todays_plan_counts_so_a_quota_cant_reset(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, "GUEST_PLANS_PER_DAY", 3)
        client.post("/api/v1/auth/register", json=ACCOUNT)
        account = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"identifier": "thandi", "password": "supersecret123"}).json()["access_token"]}
        for _ in range(3):
            client.post("/api/v1/itineraries/generate", json=PLAN, headers=account)
        _, guest = new_guest(client)
        for _ in range(2):
            assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=guest).status_code == 200

        client.post("/api/v1/auth/login", json={"identifier": "thandi", "password": "supersecret123"}, headers=guest)

        used = db_session.execute(text("SELECT used FROM plan_quota_usage")).scalars().all()
        assert used == [5]
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=account).status_code == 429

    @pytest.mark.parametrize("claim", ["register", "login"])
    def test_a_claimed_guest_token_is_rejected_afterwards(self, client, claim):
        if claim == "login":
            client.post("/api/v1/auth/register", json=ACCOUNT)
        _, headers = new_guest(client)
        if claim == "register":
            client.post("/api/v1/auth/register", json=ACCOUNT, headers=headers)
        else:
            client.post("/api/v1/auth/login", json={"identifier": "thandi", "password": "supersecret123"}, headers=headers)
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_a_guest_cant_log_in_as_a_guest(self, client):
        _, headers = new_guest(client)
        assert client.post("/api/v1/auth/login", json={"identifier": "", "password": "x"}).status_code == 401


class TestGuestLimits:
    def test_the_2nd_guest_plan_in_a_day_is_refused_with_a_sign_up_offer(self, client):
        _, headers = new_guest(client)
        assert client.post("/api/v1/itineraries/generate", json=PLAN, headers=headers).status_code == 200
        resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=headers)
        assert resp.status_code == 429
        assert resp.json()["code"] == "account_required"
        assert "Create a free account" in resp.json()["detail"]

    def test_guest_plans_per_ip_are_limited(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GUEST_SESSIONS_PER_IP_DAY", 10)
        statuses = []
        for _ in range(4):
            _, headers = new_guest(client)
            statuses.append(client.post("/api/v1/itineraries/generate", json=PLAN, headers=headers).status_code)
        assert statuses == [200, 200, 200, 429]

    def test_all_guests_share_a_daily_cap(self, client, monkeypatch):
        monkeypatch.setattr(settings, "GUEST_SESSIONS_PER_IP_DAY", 10)
        monkeypatch.setattr(settings, "GUEST_PLANS_PER_IP_DAY", 10)
        monkeypatch.setattr(settings, "GUEST_PLANS_DAY_CAP", 2)
        statuses = []
        for _ in range(3):
            _, headers = new_guest(client)
            statuses.append(client.post("/api/v1/itineraries/generate", json=PLAN, headers=headers).json().get("limit"))
        assert statuses[-1] == "all_guests"

    def test_guests_use_the_guests_quota_pool_for_google(self, client, monkeypatch):
        from app.routers import places as places_router

        pools = []

        async def fake_details(place_ids, db=None, pool="users"):
            pools.append(pool)
            return []

        monkeypatch.setattr(places_router.places_service, "get_details", fake_details)
        _, headers = new_guest(client)
        client.get("/api/v1/places?ids=ChIJsomething0001", headers=headers)
        client.post("/api/v1/auth/register", json=ACCOUNT, headers=headers)
        account = {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"identifier": "thandi", "password": "supersecret123"}).json()["access_token"]}
        client.get("/api/v1/places?ids=ChIJsomething0001", headers=account)
        assert pools == ["guests", "users"]

    def test_the_ip_is_never_stored(self, client, db_session):
        new_guest(client)
        rows = db_session.execute(text("SELECT resource FROM quota_usage")).scalars().all()
        assert rows and all("testclient" not in r for r in rows)


class TestCleanUp:
    def test_guests_idle_for_30_days_are_removed_lazily(self, client, db_session):
        old = User(is_guest=True, last_seen_at=datetime.utcnow() - timedelta(days=31))
        recent = User(is_guest=True, last_seen_at=datetime.utcnow() - timedelta(days=5))
        account = User(username="old-account", email="old@example.com", hashed_password="x", created_at=datetime.utcnow() - timedelta(days=400))
        db_session.add_all([old, recent, account])
        db_session.commit()
        start_chat(db_session, old.id)
        old_id, recent_id, account_id = old.id, recent.id, account.id

        new_guest(client)  # each new guest session clears up to 100 idle guests

        db_session.expire_all()
        assert db_session.get(User, old_id) is None
        assert db_session.query(Chat).count() == 0  # their chats go with them
        assert db_session.get(User, recent_id) is not None
        assert db_session.get(User, account_id) is not None

    def test_with_a_frozen_clock(self, db_session):
        guest = User(is_guest=True, last_seen_at=datetime(2026, 10, 1))
        db_session.add(guest)
        db_session.commit()
        assert guests.remove_idle_guests(db_session, now=datetime(2026, 10, 30)) == 0
        assert guests.remove_idle_guests(db_session, now=datetime(2026, 11, 1)) == 1


def test_an_account_row_needs_credentials(db_session):
    from sqlalchemy.exc import IntegrityError

    db_session.add(User(is_guest=False))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_a_guest_token_for_a_made_up_user_is_rejected(client):
    headers = {"Authorization": f"Bearer {create_guest_token(99999)}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
