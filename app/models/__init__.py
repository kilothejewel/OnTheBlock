from app.core.database import Base
from app.models.user import User
from app.models.hotspot import Hotspot, user_hotspots
from app.models.itinerary import Itinerary

__all__ = ["Base", "User", "Hotspot", "user_hotspots", "Itinerary"]
