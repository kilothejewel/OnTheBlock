import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Chat(Base):
    """One planning conversation (#100): its messages, Brief versions and Plan versions."""

    __tablename__ = "chats"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    city = Column(String(40), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="chats")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan", order_by="ChatMessage.id")
    briefs = relationship("BriefVersion", back_populates="chat", cascade="all, delete-orphan", order_by="BriefVersion.version")
    plan_versions = relationship("PlanVersion", back_populates="chat", cascade="all, delete-orphan", order_by="PlanVersion.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(10), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # at most 2,000 characters (schemas/chat.py)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="messages")


class BriefVersion(Base):
    """The chat's Brief (schemas/brief.py) after each change; the highest version is current."""

    __tablename__ = "briefs"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="briefs")

    __table_args__ = (UniqueConstraint("chat_id", "version", name="uq_briefs_chat_version"),)


class PlanVersion(Base):
    """
    One generated Plan in a chat. `data` holds place IDs and our own fields
    only (schemas/chat.py PlanVersionData, ADR 0002): never Google's names,
    addresses, ratings, hours or photos.
    """

    __tablename__ = "plan_versions"

    id = Column(String(36), primary_key=True, default=_uuid)
    chat_id = Column(String(36), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    brief_version = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    trace_id = Column(String(64), nullable=True)  # the planner trace (#105)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    chat = relationship("Chat", back_populates="plan_versions")
