from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ItineraryBase(BaseModel):
    title: str
    destination: str
    budget: str
    duration_days: int = 1
    items: List[Dict[str, Any]] # Timeline of planned activities/places

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
    destination: str = Field(..., description="Target location or city (e.g. 'Miami, FL')")
    budget: str = Field(..., description="Budget level ($, $$, or $$$)")
    duration_days: int = Field(1, ge=1, le=7, description="Itinerary length in days (1-7)")
    preferences: Optional[str] = Field(None, description="Optional comma-separated vibes or preferences (e.g. 'art, vegan, nightlife')")
