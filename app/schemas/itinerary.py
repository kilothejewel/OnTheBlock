from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.cities import PlannableCity

Budget = Literal["$", "$$", "$$$"]
CostBasis = Literal["fee_table", "google_price_range", "google_price_level", "category_band", "default", "beta_estimate", "unknown"]


class Stop(BaseModel):
    """One entry in a Plan's items: a place or activity at a time on a day."""

    # Keys the app doesn't know (e.g. sent by an older web build) are dropped.
    model_config = ConfigDict(extra="ignore")

    day: int = Field(1, ge=1, description="Day of the Plan, from 1")
    time: Optional[str] = Field(None, max_length=20, description="Start time as shown, e.g. '09:00 AM'")
    activity: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    estimated_cost: int = Field(0, ge=0, description="Whole amount in the Plan's currency")
    location: Optional[str] = Field(None, max_length=300)
    address: Optional[str] = Field(None, max_length=500)
    google_place_id: Optional[str] = Field(None, max_length=300)
    verified: bool = Field(False, description="True when the place was matched to a real candidate")
    category: Optional[str] = Field(None, max_length=100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_level: Optional[int] = Field(None, ge=0, le=4)
    cost_min: Optional[int] = Field(None, ge=0, description="Per person, whole units of the Plan's currency; null when unknown")
    cost_max: Optional[int] = Field(None, ge=0)
    cost_basis: Optional[CostBasis] = Field(
        None,
        description="Where the range came from (#96). beta_estimate: a rough estimate; unknown: price not confirmed",
    )


class SavedStop(Stop):
    """
    A Stop read back from a saved Plan. Plans saved before Stops were typed can
    hold other keys and fractional costs; they still load.
    """

    model_config = ConfigDict(extra="allow")

    activity: str = ""
    estimated_cost: int = 0

    @field_validator("estimated_cost", mode="before")
    @classmethod
    def _whole_cost(cls, value: Any) -> int:
        try:
            return max(0, round(float(value)))
        except (TypeError, ValueError):
            return 0

    @field_validator("price_level", mode="before")
    @classmethod
    def _known_price_level(cls, value: Any) -> Optional[int]:
        return value if isinstance(value, int) and 0 <= value <= 4 else None

    @field_validator("cost_basis", mode="before")
    @classmethod
    def _known_basis(cls, value: Any) -> Optional[str]:
        return value if value in CostBasis.__args__ else None


class ItineraryBase(BaseModel):
    title: str = Field(..., max_length=200)
    destination: str = Field(..., max_length=100)
    duration_days: int = Field(1, ge=1, le=7)
    city: Optional[str] = None  # slug of a supported city, when planned for one
    currency: Optional[str] = None  # ISO 4217 code that estimated costs are in


class ItineraryCreate(ItineraryBase):
    budget: Budget
    items: List[Stop]


class GeneratedItinerary(ItineraryBase):
    """A Plan from /itineraries/generate: not saved yet."""

    budget: Budget
    items: List[Stop]
    demo: bool = Field(False, description="True when built from Demo data")


class ItineraryResponse(ItineraryBase):
    # Read side: saved Plans keep whatever they were saved with.
    budget: str
    duration_days: int = 1
    items: List[SavedStop]
    id: int
    user_id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class ItineraryGenerate(BaseModel):
    city: PlannableCity = Field(..., description="A live or beta city's slug (e.g. 'cape-town'); see GET /cities")
    budget: Budget = Field(..., description="Budget level ($, $$, or $$$)")
    duration_days: int = Field(1, ge=1, le=7, description="Itinerary length in days (1-7)")
    preferences: Optional[str] = Field(None, max_length=200, description="Optional comma-separated vibes or preferences (e.g. 'art, vegan, nightlife')")
