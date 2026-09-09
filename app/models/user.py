from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Legacy Supabase identifier; retained (nullable) for backwards compatibility,
    # no longer populated now that auth is handled locally via JWT.
    supabase_uid = Column(String, unique=True, index=True, nullable=True)

    # Relationships
    saved_hotspots = relationship("Hotspot", secondary="user_hotspots", back_populates="saved_by_users")
    itineraries = relationship("Itinerary", back_populates="user", cascade="all, delete-orphan")
