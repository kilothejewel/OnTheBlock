"""
The free-quota guard: ask before every Google or LLM call, and stop just
before each free allowance.

    if not quota.take("google.details_enterprise", pool="guests"):
        ...  # degrade: e.g. Stop marked "rating and hours not confirmed"

Usage lives in the database (`quota_usage`), never in a process, so every
worker and the GitHub Actions jobs share one count. A take counts against two
rows in one transaction:

- the day row for the resource (all pools together), against the daily limit
- the month row for the resource and pool, against that pool's share of the
  monthly limit (`users` gets what the other pools' caps leave)

Each row is bumped with a conditional upsert (`... ON CONFLICT DO UPDATE ...
WHERE used + n <= limit RETURNING used`). Postgres locks the row it updates,
so concurrent takes wait for each other and the count can't overshoot; if
either row would go over, the transaction rolls back and nothing is counted.
Days and months are UTC.

Limits come from settings (QUOTA_LIMITS, QUOTA_POOL_CAPS). A resource with no
limits configured is refused: an unknown call is never free by accident.
"""

import logging
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional

from sqlalchemy import Engine
from sqlalchemy.dialects import postgresql, sqlite

from app.core.config import settings
from app.core.database import engine as app_engine
from app.models.quota import QuotaUsage

log = logging.getLogger(__name__)

POOLS = ("users", "guests", "eval")
ALL_POOLS = "all"  # the pool on day rows

_table = QuotaUsage.__table__


class _Refused(Exception):
    """A row is at its limit: roll the take back."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Quota:
    def __init__(
        self,
        bind: Engine,
        limits: Optional[Dict[str, Dict[str, int]]] = None,
        pool_caps: Optional[Dict[str, Dict[str, int]]] = None,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.bind = bind
        self.limits = settings.QUOTA_LIMITS if limits is None else limits
        self.pool_caps = settings.QUOTA_POOL_CAPS if pool_caps is None else pool_caps
        self.clock = clock

    def limits_for(self, resource: str) -> Optional[Dict[str, int]]:
        """The resource's limits: an exact entry, else the longest matching "prefix.*" entry."""
        if resource in self.limits:
            return self.limits[resource]
        matches = [key for key in self.limits if key.endswith(".*") and resource.startswith(key[:-1])]
        return self.limits[max(matches, key=len)] if matches else None

    def month_limit(self, resource: str, pool: str) -> Optional[int]:
        """The pool's share of the resource's monthly limit (None: no monthly limit)."""
        limits = self.limits_for(resource) or {}
        total = limits.get("month")
        if total is None:
            return None
        if pool == "users":
            reserved = sum(caps.get(resource, 0) for name, caps in self.pool_caps.items() if name != "users")
            return max(total - reserved, 0)
        return min(self.pool_caps.get(pool, {}).get(resource, 0), total)

    def _rows(self, resource: str, pool: str, today: date):
        """(period, starts, pool, limit) for the rows a take counts against."""
        limits = self.limits_for(resource) or {}
        return [
            ("day", today, ALL_POOLS, limits.get("day")),
            ("month", today.replace(day=1), pool, self.month_limit(resource, pool)),
        ]

    def take(self, resource: str, n: int = 1, pool: str = "users") -> bool:
        """
        Count `n` uses of `resource` for `pool` if every limit allows it.
        True means go ahead; False means don't make the call (and nothing was counted).
        """
        if pool not in POOLS:
            raise ValueError(f"Unknown quota pool {pool!r}; use one of {POOLS}")
        if n < 1:
            raise ValueError("n must be at least 1")
        if self.limits_for(resource) is None:
            log.warning("quota refused %s: no limits configured", resource)
            return False

        rows = self._rows(resource, pool, self.clock().astimezone(timezone.utc).date())
        if any(limit is not None and n > limit for *_, limit in rows):
            return False

        try:
            with self.bind.begin() as conn:
                insert = postgresql.insert if conn.dialect.name == "postgresql" else sqlite.insert
                for period, starts, row_pool, limit in rows:
                    stmt = insert(_table).values(
                        period=period, starts=starts, resource=resource, pool=row_pool,
                        used=n, updated_at=datetime.utcnow(),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[_table.c.period, _table.c.starts, _table.c.resource, _table.c.pool],
                        set_={"used": _table.c.used + n, "updated_at": stmt.excluded.updated_at},
                        where=None if limit is None else (_table.c.used + n <= limit),
                    ).returning(_table.c.used)
                    if conn.execute(stmt).first() is None:
                        raise _Refused()
        except _Refused:
            log.info("quota refused %s for %s: at its limit", resource, pool)
            return False
        return True

    def report(self) -> List[Dict[str, object]]:
        """
        Today's and this month's use of every resource that has been used, with
        its limit: for the admin endpoint (#115) and the planner trace (#105).
        """
        today = self.clock().astimezone(timezone.utc).date()
        current = {("day", today), ("month", today.replace(day=1))}
        with self.bind.connect() as conn:
            rows = conn.execute(_table.select().order_by(_table.c.resource, _table.c.period, _table.c.pool)).all()
        report = []
        for row in rows:
            if (row.period, row.starts) not in current:
                continue
            limits = self.limits_for(row.resource) or {}
            limit = limits.get("day") if row.period == "day" else self.month_limit(row.resource, row.pool)
            report.append({
                "resource": row.resource, "period": row.period, "starts": row.starts.isoformat(),
                "pool": row.pool, "used": row.used, "limit": limit,
            })
        return report


quota = Quota(app_engine)
