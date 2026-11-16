from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String

from app.core.database import Base


class CityRequest(Base):
    """A city someone searched for that we don't cover yet (#89): what they typed, who, when."""

    __tablename__ = "city_requests"

    id = Column(Integer, primary_key=True)
    text = Column(String(80), nullable=False)
    # Kept when the user (or an idle guest) is deleted, so demand counts survive.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (Index("ix_city_requests_user_id_created_at", "user_id", "created_at"),)
