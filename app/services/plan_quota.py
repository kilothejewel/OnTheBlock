"""
Each user's daily quota of new Plans.

Counted in the database (`plan_quota_usage`), so a restart or another worker
doesn't reset it, and per UTC day. Taking a Plan is one conditional upsert
(`... WHERE used < limit RETURNING used`), so two requests at once can't both
take the last one. A Plan that fails to generate is given back.

This is each user's own quota; the global daily Plan cap is #115's.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.plan_quota import PlanQuotaUsage
from app.models.user import User

_table = PlanQuotaUsage.__table__


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def daily_plan_limit(user: User) -> int:
    """The user's daily quota: guests (#125) get a lower one."""
    return settings.GUEST_PLANS_PER_DAY if getattr(user, "is_guest", False) else settings.PLANS_PER_USER_PER_DAY


@dataclass(frozen=True)
class PlanQuota:
    allowed: bool
    limit: int
    day: date  # the UTC day it counted against
    used: int  # after this take, if allowed
    resets_at: datetime  # next 00:00 UTC

    @property
    def retry_after_seconds(self) -> int:
        return max(int((self.resets_at - utc_now()).total_seconds()) + 1, 1)


def _today_and_reset() -> tuple:
    now = utc_now()
    today = now.date()
    return today, datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone.utc)


def take_plan(db: Session, user: User) -> PlanQuota:
    """Count one new Plan for the user today, if their quota allows it."""
    today, resets_at = _today_and_reset()
    limit = daily_plan_limit(user)
    if limit < 1:
        return PlanQuota(False, limit, today, 0, resets_at)

    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    stmt = insert(_table).values(user_id=user.id, day=today, used=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[_table.c.user_id, _table.c.day],
        set_={"used": _table.c.used + 1},
        where=_table.c.used < limit,
    ).returning(_table.c.used)
    row = db.execute(stmt).first()
    db.commit()
    if row is None:
        return PlanQuota(False, limit, today, limit, resets_at)
    return PlanQuota(True, limit, today, row.used, resets_at)


def give_back_plan(db: Session, user: User, day: date) -> None:
    """Undo a take for a Plan that failed, so it doesn't count."""
    db.execute(
        update(_table)
        .where(_table.c.user_id == user.id, _table.c.day == day, _table.c.used > 0)
        .values(used=_table.c.used - 1)
    )
    db.commit()
