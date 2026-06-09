from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class HotspotBase(BaseModel):
    google_place_id: str
    name: str
    rating: Optional[float] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_level: Optional[int] = None
    types: Optional[str] = None

class HotspotCreate(HotspotBase):
    pass

class HotspotResponse(HotspotBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
