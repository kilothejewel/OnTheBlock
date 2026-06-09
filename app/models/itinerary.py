from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Itinerary(Base):
    __tablename__ = "itineraries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    budget = Column(String, nullable=False) # Budget category, e.g. "$", "$$", "$$$"
    duration_days = Column(Integer, default=1)
    items = Column(JSON, nullable=False) # JSON list containing details of each day's itinerary stops
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="itineraries")
