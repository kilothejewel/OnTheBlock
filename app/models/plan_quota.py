from sqlalchemy import Column, Date, ForeignKey, Integer

from app.core.database import Base


class PlanQuotaUsage(Base):
    """How many new Plans a user has started on a UTC day (app/services/plan_quota.py)."""

    __tablename__ = "plan_quota_usage"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day = Column(Date, primary_key=True)
    used = Column(Integer, nullable=False, default=0)
