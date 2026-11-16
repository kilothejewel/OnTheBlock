"""
Chats, their messages, Brief versions and Plan versions (#88).

`PlanVersionData` is what `plan_versions.data` holds: place IDs and our own
fields (times, Slot, costs, copy, badges). It forbids any other key, so a
Google name, address, rating, hours or photo can't be stored by accident
(ADR 0002); display fields come from the catalogue and the live check (#29,
#93) each time a Plan is shown.
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

MAX_MESSAGE_CHARS = 2000


class TravelLeg(BaseModel):
    """Getting from this Stop to the next (#97)."""

    model_config = ConfigDict(extra="forbid")
    mode: Literal["walk", "e_hailing", "car"]
    minutes: int = Field(ge=0)
    cost_min: int = Field(0, ge=0)
    cost_max: int = Field(0, ge=0)


class StoredStop(BaseModel):
    """One Stop of a Plan version, as stored: IDs and our own fields only."""

    model_config = ConfigDict(extra="forbid")
    slot_id: str
    slot_kind: str  # breakfast, lunch, dinner, activity, nightlife
    day: int = Field(1, ge=1)
    start_time: str  # "HH:MM" on the city's clock
    end_time: Optional[str] = None
    catalogue_place_id: Optional[int] = None  # places.id (#119)
    google_place_id: Optional[str] = None
    title: str = Field(max_length=120)  # our copy (compose, #98)
    description: str = Field("", max_length=600)
    cost_min: Optional[int] = Field(None, ge=0)  # rands per person (#96)
    cost_max: Optional[int] = Field(None, ge=0)
    cost_basis: Optional[str] = None  # where the estimate came from, e.g. "category band"
    badges: List[str] = Field(default_factory=list)  # e.g. "hours not confirmed", "Locals recommend"
    travel_to_next: Optional[TravelLeg] = None


class PlanVersionData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intro: str = Field("", max_length=600)
    stops: List[StoredStop]
    total_min: Optional[int] = Field(None, ge=0)
    total_max: Optional[int] = Field(None, ge=0)
    notes: List[str] = Field(default_factory=list)  # e.g. why a Stop was dropped


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_MESSAGE_CHARS)
    created_at: datetime


class BriefVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    version: int
    data: dict
    created_at: datetime


class PlanVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    brief_version: int
    data: PlanVersionData
    trace_id: Optional[str] = None
    created_at: datetime


class ChatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    city: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageOut] = []
    plan_versions: List[PlanVersionOut] = []
