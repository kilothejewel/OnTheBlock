"""
The Brief: what someone wants from a Plan, gathered over a chat (GLOSSARY).

The chat's intake step (#91) turns each message into a `BriefPatch`, and
`apply_patch` merges it into the Brief. Validation messages are written for
people, since they can end up in the chat.
"""

from datetime import date, datetime, time, timezone
from typing import Dict, List, Literal, Optional, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.cities import CITIES, PlannableCity
from app.core.config import settings
from app.services.interests import INTERESTS

Mode = Literal["day", "night", "full_day"]
BudgetBasis = Literal["per_person", "total"]
Transport = Literal["e_hailing", "own_car", "walk_short"]
Dietary = Literal["vegan", "halaal", "kosher", "vegetarian", "gluten_free"]
Accessibility = Literal["none", "step_free"]
Pace = Literal["relaxed", "packed"]

MAX_DAYS_AHEAD = 14
# Where each Mode starts and ends when the Brief doesn't say. A night ends after midnight.
MODE_HOURS: Dict[str, Tuple[time, time]] = {
    "day": (time(9, 0), time(18, 0)),
    "night": (time(19, 0), time(2, 0)),
    "full_day": (time(9, 0), time(23, 59)),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def today_in(city_slug: str) -> date:
    """Today on the city's clock, not the server's."""
    return utc_now().astimezone(ZoneInfo(CITIES[city_slug].timezone)).date()


class InterestWeight(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interest: str
    weight: float = Field(1.0, ge=0, le=1)

    @field_validator("interest")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in INTERESTS:
            raise ValueError(f"'{value}' isn't one of our Interests")
        return value


def _short_texts(values: List[str]) -> List[str]:
    values = [v.strip() for v in values if v and v.strip()]
    if len(values) > 5:
        raise ValueError("at most 5 items")
    if any(len(v) > 60 for v in values):
        raise ValueError("each item can be at most 60 characters")
    return values


class _BriefFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("must_include", "avoid", check_fields=False)
    @classmethod
    def _limit_texts(cls, values):
        return values if values is None else _short_texts(values)

    @field_validator("dietary", check_fields=False)
    @classmethod
    def _unique_dietary(cls, values):
        return values if values is None else list(dict.fromkeys(values))

    @field_validator("interests", check_fields=False)
    @classmethod
    def _unique_interests(cls, values):
        if values is None:
            return values
        merged: Dict[str, InterestWeight] = {}
        for item in values:
            if item.interest not in merged or item.weight > merged[item.interest].weight:
                merged[item.interest] = item
        return list(merged.values())


class Brief(_BriefFields):
    """Everything the planner needs to know about the Plan someone wants."""

    city: PlannableCity
    area: Optional[str] = Field(None, description="An Area slug of the city; null lets the planner choose")
    date: date
    start_time: Optional[time] = Field(None, description="Defaults from mode")
    end_time: Optional[time] = Field(None, description="Defaults from mode; before start_time means after midnight")
    mode: Mode = "day"
    party_size: int = Field(1, ge=1, le=12)
    budget_amount: Optional[int] = Field(None, ge=0, description="In the city's currency (ZAR in South Africa)")
    budget_basis: BudgetBasis = "per_person"
    interests: List[InterestWeight] = Field(default_factory=list)
    must_include: List[str] = Field(default_factory=list, description="Free text, e.g. Lion's Head")
    avoid: List[str] = Field(default_factory=list, description="Free text, e.g. no alcohol")
    transport: Transport = "e_hailing"
    dietary: List[Dietary] = Field(default_factory=list)
    accessibility: Accessibility = "none"
    pace: Pace = "relaxed"

    @model_validator(mode="after")
    def _combinations(self):
        city = CITIES[self.city]
        today = today_in(self.city)
        if self.date < today:
            raise ValueError(f"{self.date:%d %B %Y} has already passed in {city.name}")
        if (self.date - today).days > MAX_DAYS_AHEAD:
            raise ValueError(f"Plans can be made up to {MAX_DAYS_AHEAD} days ahead")
        if self.area is not None:
            from app.services.areas import areas_for

            known = {a.slug for a in areas_for(self.city)}
            if known and self.area not in known:
                raise ValueError(f"'{self.area}' isn't an Area of {city.name}")
        if self.budget_amount is not None:
            cap = settings.BUDGET_MAX.get(city.currency)
            if cap is not None and self.budget_amount > cap:
                raise ValueError(f"A budget above {city.currency} {cap:,} is more than we plan for")
        if self.budget_basis == "total" and "party_size" not in self.model_fields_set:
            raise ValueError("A total budget needs the party size, so it can be split per person")
        return self

    def window(self) -> Tuple[time, time]:
        """When the Plan starts and ends, from the Brief or its mode's defaults."""
        start, end = MODE_HOURS[self.mode]
        return self.start_time or start, self.end_time or end

    def budget_per_person(self) -> Optional[int]:
        if self.budget_amount is None:
            return None
        if self.budget_basis == "total":
            return self.budget_amount // self.party_size
        return self.budget_amount


class BriefPatch(_BriefFields):
    """A change to a Brief: only the fields it sets change. null clears a field that can be empty."""

    city: Optional[PlannableCity] = None
    area: Optional[str] = None
    date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    mode: Optional[Mode] = None
    party_size: Optional[int] = Field(None, ge=1, le=12)
    budget_amount: Optional[int] = Field(None, ge=0)
    budget_basis: Optional[BudgetBasis] = None
    interests: Optional[List[InterestWeight]] = None
    must_include: Optional[List[str]] = None
    avoid: Optional[List[str]] = None
    transport: Optional[Transport] = None
    dietary: Optional[List[Dietary]] = None
    accessibility: Optional[Accessibility] = None
    pace: Optional[Pace] = None


# Brief fields that may be empty, so a patch can clear them with null.
_NULLABLE = {"area", "start_time", "end_time", "budget_amount"}


class BriefError(ValueError):
    """A Brief that doesn't hold together; `messages` are readable, one per problem."""

    def __init__(self, messages: List[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


def readable_errors(exc: ValidationError) -> List[str]:
    messages = []
    for error in exc.errors():
        message = error["msg"].removeprefix("Value error, ")
        field = ".".join(str(part) for part in error["loc"])
        messages.append(f"{field}: {message}" if field else message)
    return messages


def apply_patch(brief: Brief, patch: BriefPatch) -> Brief:
    """
    The Brief with the patch's fields changed and every other field kept,
    validated again as a whole. Raises BriefError with readable messages.
    """
    changes = {}
    for name in patch.model_fields_set:
        value = getattr(patch, name)
        if value is None and name not in _NULLABLE:
            continue  # null only clears fields that can be empty
        changes[name] = value
    merged = brief.model_dump(exclude_unset=True) | patch.model_dump(include=set(changes))
    try:
        return Brief.model_validate(merged)
    except ValidationError as exc:
        raise BriefError(readable_errors(exc)) from None
