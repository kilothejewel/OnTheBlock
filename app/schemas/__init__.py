from app.schemas.hotspot import HotspotBase, HotspotCreate, HotspotResponse
from app.schemas.itinerary import ItineraryBase, ItineraryCreate, ItineraryResponse, ItineraryGenerate
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse

__all__ = [
    "HotspotBase",
    "HotspotCreate",
    "HotspotResponse",
    "ItineraryBase",
    "ItineraryCreate",
    "ItineraryResponse",
    "ItineraryGenerate",
    "Token",
    "UserCreate",
    "UserLogin",
    "UserResponse",
]
