"""The chat tables (#88): chats, messages, Brief versions, Plan versions."""

import json

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.chat import BriefVersion, Chat, ChatMessage, PlanVersion
from app.models.itinerary import Itinerary
from app.models.user import User
from app.schemas.chat import ChatOut, PlanVersionData

STOP = {
    "slot_id": "s1", "slot_kind": "breakfast", "start_time": "09:00", "end_time": "10:00",
    "catalogue_place_id": 12, "google_place_id": "ChIJtruth00001", "title": "Truth Coffee",
    "description": "Steampunk coffee bar in the City Bowl.", "cost_min": 80, "cost_max": 150,
    "cost_basis": "category band", "badges": ["hours not confirmed"],
    "travel_to_next": {"mode": "walk", "minutes": 8},
}

# What Google's Place Details would call its display fields: none may be stored.
GOOGLE_DISPLAY_FIELDS = ["displayName", "formattedAddress", "address", "name", "rating", "userRatingCount",
                         "regularOpeningHours", "opening_hours", "photos", "photo_url", "priceLevel", "reviews",
                         "websiteUri", "nationalPhoneNumber"]


@pytest.fixture
def user(db_session):
    user = User(username="sam", email="sam@example.com", hashed_password="x")
    db_session.add(user)
    db_session.commit()
    return user


def a_chat(db_session, user):
    chat = Chat(user_id=user.id, city="cape-town")
    chat.messages.append(ChatMessage(role="user", content="A hike and a jol in Cape Town"))
    chat.briefs.append(BriefVersion(version=1, data={"city": "cape-town", "date": "2026-11-20"}))
    chat.plan_versions.append(PlanVersion(brief_version=1, data=PlanVersionData(stops=[STOP]).model_dump()))
    db_session.add(chat)
    db_session.commit()
    return chat


def test_a_chat_keeps_its_messages_briefs_and_plan_versions(db_session, user):
    chat = a_chat(db_session, user)
    assert len(chat.id) == 36
    out = ChatOut.model_validate(chat)
    assert [m.content for m in out.messages] == ["A hike and a jol in Cape Town"]
    assert out.plan_versions[0].data.stops[0].google_place_id == "ChIJtruth00001"


def test_deleting_a_user_cascades_to_their_chats(db_session, user):
    a_chat(db_session, user)
    db_session.delete(user)
    db_session.commit()
    for table in ("chats", "chat_messages", "briefs", "plan_versions"):
        assert db_session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 0, table


def test_brief_versions_are_unique_per_chat(db_session, user):
    chat = a_chat(db_session, user)
    db_session.add(BriefVersion(chat_id=chat.id, version=1, data={}))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("field", GOOGLE_DISPLAY_FIELDS)
def test_no_google_display_field_can_be_stored_in_a_plan_version(field):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PlanVersionData(stops=[{**STOP, field: "from Google"}])
    with pytest.raises(ValidationError):
        PlanVersionData(stops=[STOP], **{field: "from Google"})


def test_a_stored_plan_version_holds_ids_and_our_own_fields_only(db_session, user):
    chat = a_chat(db_session, user)
    stored = json.loads(db_session.execute(text("SELECT data FROM plan_versions")).scalar())
    keys = set(stored) | {k for stop in stored["stops"] for k in stop}
    assert not keys & set(GOOGLE_DISPLAY_FIELDS)
    assert stored["stops"][0]["google_place_id"] == "ChIJtruth00001"


def test_an_itinerary_can_point_at_a_plan_version_and_old_ones_still_load(db_session, user):
    chat = a_chat(db_session, user)
    old = Itinerary(user_id=user.id, title="Old", destination="Tokyo", budget="$$", items=[])
    new = Itinerary(user_id=user.id, title="New", destination="Cape Town", budget="$$", items=[],
                    plan_version_id=chat.plan_versions[0].id, mode="night")
    db_session.add_all([old, new])
    db_session.commit()
    assert (old.plan_version_id, old.mode) == (None, None)
    assert new.plan_version_id == chat.plan_versions[0].id
