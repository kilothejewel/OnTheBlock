from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, false as sa_false
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Empty only for guests (#125); a check constraint holds accounts to all three.
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Someone using the app without an account, with their own guest session (#125).
    is_guest = Column(Boolean, nullable=False, default=False, server_default=sa_false())
    last_seen_at = Column(DateTime, nullable=True)  # guests idle for 30 days are removed
    # Legacy Supabase identifier; retained (nullable) for backwards compatibility,
    # no longer populated now that auth is handled locally via JWT.
    supabase_uid = Column(String, unique=True, index=True, nullable=True)

    # Relationships
    saved_hotspots = relationship("Hotspot", secondary="user_hotspots", back_populates="saved_by_users")
    itineraries = relationship("Itinerary", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "is_guest OR (email IS NOT NULL AND username IS NOT NULL AND hashed_password IS NOT NULL)",
            name="ck_users_account_has_credentials",
        ),
    )
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
