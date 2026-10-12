from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime

from app.core.cities import CitySlug

Budget = Literal["$", "$$", "$$$"]

class ItineraryBase(BaseModel):
    title: str = Field(..., max_length=200)
    destination: str = Field(..., max_length=100)
    budget: str
    duration_days: int = 1
    items: List[Dict[str, Any]] # Timeline of planned activities/places
    city: Optional[str] = None  # slug of a supported city, when planned for one
    currency: Optional[str] = None  # ISO 4217 code that estimated costs are in

class ItineraryCreate(ItineraryBase):
    pass

class ItineraryResponse(ItineraryBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

class ItineraryGenerate(BaseModel):
    city: CitySlug = Field(..., description="Supported city slug (e.g. 'cape-town')")
    budget: Budget = Field(..., description="Budget level ($, $$, or $$$)")
    duration_days: int = Field(1, ge=1, le=7, description="Itinerary length in days (1-7)")
    preferences: Optional[str] = Field(None, max_length=200, description="Optional comma-separated vibes or preferences (e.g. 'art, vegan, nightlife')")
