"""The free-quota guard (#121): limits per UTC day and month, pools, and atomic takes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.services.quota import Quota
from tests.conftest import TEST_DATABASE_URL

LIMITS = {
    "google.details_enterprise": {"day": 5, "month": 12},
    "google.text_ids": {"day": 3},
    "google.counted": {},
    "llm.gemini.*": {"day": 2},
}
POOL_CAPS = {"eval": {"google.details_enterprise": 3}, "guests": {"google.details_enterprise": 2}}


class FrozenClock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at


@pytest.fixture
def clock():
    return FrozenClock(datetime(2026, 11, 30, 23, 0, tzinfo=timezone.utc))


@pytest.fixture
def engine(db_session):
    """The test database the suite's tables are created in (conftest)."""
    return db_session.get_bind()


@pytest.fixture
def guard(engine, clock):
    return Quota(engine, limits=LIMITS, pool_caps=POOL_CAPS, clock=clock)


def take_all(guard, resource, times, **kwargs):
    return [guard.take(resource, **kwargs) for _ in range(times)]


def test_takes_stop_at_the_daily_limit(guard):
    assert take_all(guard, "google.details_enterprise", 6) == [True] * 5 + [False]


def test_a_refused_take_counts_nothing(guard):
    take_all(guard, "google.text_ids", 3)
    assert guard.take("google.text_ids") is False
    day = [row for row in guard.report() if row["period"] == "day"]
    assert day == [{"resource": "google.text_ids", "period": "day", "starts": "2026-11-30", "pool": "all", "used": 3, "limit": 3}]


def test_n_counts_several_uses_at_once_and_never_partly(guard):
    assert guard.take("google.details_enterprise", n=4) is True
    assert guard.take("google.details_enterprise", n=2) is False  # would make 6 of 5
    assert guard.take("google.details_enterprise", n=1) is True
    assert guard.take("google.details_enterprise", n=99) is False


def test_the_monthly_limit_holds_across_days(guard, clock):
    clock.at = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    used = 0
    for _ in range(3):  # three days, five a day; the users' share of the month is 12 - 3 - 2 = 7
        used += sum(take_all(guard, "google.details_enterprise", 5))
        clock.at += timedelta(days=1)
    assert used == 7


def test_day_rollover_is_at_midnight_utc(guard, clock):
    take_all(guard, "google.text_ids", 3)
    assert guard.take("google.text_ids") is False

    clock.at = datetime(2026, 11, 30, 23, 59, 59, tzinfo=timezone.utc)
    assert guard.take("google.text_ids") is False
    clock.at = datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert guard.take("google.text_ids") is True


def test_utc_decides_the_day_whatever_the_clocks_zone(guard, clock):
    take_all(guard, "google.text_ids", 3)
    # 01:00 on 1 December in Johannesburg is still 30 November, 23:00 UTC.
    clock.at = datetime(2026, 12, 1, 1, 0, tzinfo=timezone(timedelta(hours=2)))
    assert guard.take("google.text_ids") is False


def test_month_rollover_starts_a_new_allowance(guard, clock):
    clock.at = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)
    take_all(guard, "google.details_enterprise", 5)
    clock.at += timedelta(days=1)
    take_all(guard, "google.details_enterprise", 2)
    clock.at += timedelta(days=1)
    assert guard.take("google.details_enterprise") is False  # 7 of the users' 7 this month

    clock.at = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
    assert take_all(guard, "google.details_enterprise", 5) == [True] * 5


def test_eval_and_guests_cannot_eat_into_the_users_pool(guard, clock):
    clock.at = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
    assert take_all(guard, "google.details_enterprise", 5, pool="eval") == [True] * 3 + [False] * 2
    clock.at += timedelta(days=1)
    assert take_all(guard, "google.details_enterprise", 5, pool="guests") == [True] * 2 + [False] * 3

    users = 0
    for _ in range(3):
        clock.at += timedelta(days=1)
        users += sum(take_all(guard, "google.details_enterprise", 5))
    assert users == 7  # the whole users' share is still there
    assert 3 + 2 + users == LIMITS["google.details_enterprise"]["month"]


def test_a_pool_without_a_cap_cannot_use_a_monthly_resource(engine, clock):
    guard = Quota(engine, limits=LIMITS, pool_caps={}, clock=clock)
    assert guard.take("google.details_enterprise", pool="eval") is False
    assert guard.take("google.details_enterprise", pool="users") is True


def test_every_pool_shares_the_daily_limit(guard, clock):
    clock.at = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
    assert take_all(guard, "google.details_enterprise", 2, pool="guests") == [True, True]
    assert take_all(guard, "google.details_enterprise", 4) == [True, True, True, False]


def test_a_resource_with_no_limits_is_refused_and_one_with_empty_limits_is_counted(guard):
    assert guard.take("google.unknown_sku") is False
    assert take_all(guard, "google.counted", 50) == [True] * 50


def test_llm_models_match_a_prefix_entry(guard):
    assert take_all(guard, "llm.gemini.gemini-flash", 3) == [True, True, False]
    assert take_all(guard, "llm.gemini.gemini-flash-lite", 2) == [True, True]  # each model on its own
    assert guard.take("llm.groq.llama") is False  # no entry for groq here


def test_an_unknown_pool_is_a_programming_error(guard):
    with pytest.raises(ValueError):
        guard.take("google.text_ids", pool="admins")
    with pytest.raises(ValueError):
        guard.take("google.text_ids", n=0)


def test_report_lists_this_days_and_months_use_with_limits(guard, clock):
    clock.at = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    guard.take("google.details_enterprise")  # last month: not reported
    clock.at = datetime(2026, 11, 30, 12, 0, tzinfo=timezone.utc)
    guard.take("google.details_enterprise", pool="eval")
    guard.take("google.details_enterprise", n=2)

    assert guard.report() == [
        {"resource": "google.details_enterprise", "period": "day", "starts": "2026-11-30", "pool": "all", "used": 3, "limit": 5},
        {"resource": "google.details_enterprise", "period": "month", "starts": "2026-11-01", "pool": "eval", "used": 1, "limit": 3},
        {"resource": "google.details_enterprise", "period": "month", "starts": "2026-11-01", "pool": "users", "used": 2, "limit": 7},
    ]


def test_the_default_limits_stay_under_each_free_allowance(engine):
    limits = settings.QUOTA_LIMITS
    assert limits["google.details_enterprise"] == {"day": 30, "month": 950}
    assert limits["google.details_pro"] == {"day": 160, "month": 4750}
    assert limits["google.photos"] == {"day": 30, "month": 950}
    assert limits["google.text_search_enterprise"] == {"day": 30, "month": 900}
    assert limits["google.text_ids"] == {"day": 1000}
    assert settings.QUOTA_POOL_CAPS["eval"]["google.details_enterprise"] == 200
    assert settings.QUOTA_POOL_CAPS["guests"]["google.details_enterprise"] == 150
    guard = Quota(engine)
    for resource, caps in [("google.details_enterprise", 1000), ("google.details_pro", 5000), ("google.photos", 1000)]:
        pools = sum(guard.month_limit(resource, pool) for pool in ("users", "guests", "eval"))
        assert pools <= limits[resource]["month"] < caps


@pytest.mark.skipif(TEST_DATABASE_URL.startswith("sqlite"), reason="needs Postgres: concurrent writers")
def test_concurrent_takes_never_exceed_the_limit(engine, clock):
    guard = Quota(engine, limits={"google.details_enterprise": {"day": 25, "month": 40}}, pool_caps={}, clock=clock)

    with ThreadPoolExecutor(max_workers=16) as workers:
        results = list(workers.map(lambda _: guard.take("google.details_enterprise"), range(200)))

    assert results.count(True) == 25
    with engine.connect() as conn:
        used = conn.execute(text("SELECT used FROM quota_usage WHERE period = 'day'")).scalar()
    assert used == 25
