from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String

from app.core.database import Base


class QuotaUsage(Base):
    """
    How much of a free allowance has been used (app/services/quota.py).

    One row per period: a day row counts every pool together against the daily
    limit; a month row counts one pool against its share of the monthly limit.
    """

    __tablename__ = "quota_usage"

    period = Column(String(5), primary_key=True)  # "day" or "month"
    starts = Column(Date, primary_key=True)  # the UTC day, or the first day of the UTC month
    resource = Column(String(100), primary_key=True)  # e.g. "google.details_enterprise"
    pool = Column(String(20), primary_key=True)  # "users", "guests", "eval"; "all" on day rows
    used = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
