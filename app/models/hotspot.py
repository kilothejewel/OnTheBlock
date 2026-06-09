from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

# Association table for User-Hotspot many-to-many relationship
user_hotspots = Table(
    "user_hotspots",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("hotspot_id", Integer, ForeignKey("hotspots.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime, default=datetime.utcnow)
)

class Hotspot(Base):
    __tablename__ = "hotspots"

    id = Column(Integer, primary_key=True, index=True)
    google_place_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    rating = Column(Float, nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    price_level = Column(Integer, nullable=True)
    types = Column(String, nullable=True) # Comma-separated string of place types
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    saved_by_users = relationship("User", secondary=user_hotspots, back_populates="saved_hotspots")
