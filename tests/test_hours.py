"""Opening hours against a Stop's time, in the city's time zone (#37). Hours are mocked Google periods."""

import time
from datetime import datetime, timezone

import pytest

from app.core.cities import get_city
from app.services.hours import HOURS_NOT_CONFIRMED, decide_for_slot, is_open, local_start

CAPE_TOWN = get_city("cape-town").timezone  # Africa/Johannesburg, UTC+2 all year
LONDON = get_city("london").timezone

# 2026-11-20 is a Friday; 2026-11-21 a Saturday; 2026-11-22 a Sunday.
FRIDAY = datetime(2026, 11, 20)


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute)


def period(open_day, open_hm, close_day=None, close_hm=None):
    """A Google period. Days: 0 = Sunday ... 6 = Saturday."""
    p = {"open": {"day": open_day, "hour": open_hm[0], "minute": open_hm[1]}}
    if close_day is not None:
        p["close"] = {"day": close_day, "hour": close_hm[0], "minute": close_hm[1]}
    return p


# A cafe open 08:00-16:00 Monday to Friday; closed at weekends (no period).
CAFE = {"periods": [period(d, (8, 0), d, (16, 0)) for d in range(1, 6)]}
# A club open 22:00-04:00 Friday and Saturday nights.
CLUB = {"periods": [period(5, (22, 0), 6, (4, 0)), period(6, (22, 0), 0, (4, 0))]}
# Open 24 hours: Google sends one period that opens Sunday 00:00 and never closes.
ALWAYS = {"periods": [period(0, (0, 0))]}


class TestIsOpen:
    def test_open_for_the_whole_visit(self):
        assert is_open(CAFE, at(20, 9), 90, CAPE_TOWN) is True

    def test_a_visit_that_runs_past_closing_is_not_open(self):
        assert is_open(CAFE, at(20, 15), 90, CAPE_TOWN) is False

    def test_before_opening(self):
        assert is_open(CAFE, at(20, 7, 30), 30, CAPE_TOWN) is False

    def test_a_visit_ending_exactly_at_closing_fits(self):
        assert is_open(CAFE, at(20, 14, 30), 90, CAPE_TOWN) is True

    def test_a_day_with_no_period_is_closed(self):
        assert is_open(CAFE, at(21, 10), 60, CAPE_TOWN) is False

    @pytest.mark.parametrize("start, minutes, expected", [
        (at(20, 23), 120, True),    # Friday 23:00-01:00
        (at(21, 2), 60, True),      # Saturday 02:00-03:00, still Friday night's period
        (at(21, 3, 30), 60, False),  # runs past 04:00
        (at(22, 1), 120, True),     # Sunday 01:00-03:00: Saturday night wraps into Sunday
        (at(20, 21), 60, False),    # Friday 21:00, before it opens
        (at(19, 23), 60, False),    # Thursday night: no period
    ])
    def test_overnight_periods(self, start, minutes, expected):
        assert is_open(CLUB, start, minutes, CAPE_TOWN) is expected

    @pytest.mark.parametrize("start", [at(22, 3), at(20, 12), at(21, 23, 59)])
    def test_open_24_hours(self, start):
        assert is_open(ALWAYS, start, 600, CAPE_TOWN) is True

    @pytest.mark.parametrize("hours", [None, {}, {"periods": []}, {"periods": [{"close": {"day": 1}}]}])
    def test_no_hours_is_unknown(self, hours):
        assert is_open(hours, at(20, 9), 60, CAPE_TOWN) is None

    def test_a_zero_minute_visit_checks_the_start(self):
        assert is_open(CAFE, at(20, 8), 0, CAPE_TOWN) is True
        assert is_open(CAFE, at(20, 16), 0, CAPE_TOWN) is False


class TestTimeZone:
    def test_an_aware_start_is_read_on_the_citys_clock(self):
        # 07:30 UTC on Friday is 09:30 in Cape Town (open), and 07:30 in London (closed).
        start = datetime(2026, 11, 20, 7, 30, tzinfo=timezone.utc)
        assert is_open(CAFE, start, 30, CAPE_TOWN) is True
        assert is_open(CAFE, start, 30, LONDON) is False

    def test_the_servers_time_zone_makes_no_difference(self, monkeypatch):
        if not hasattr(time, "tzset"):
            pytest.skip("time.tzset is Unix-only")
        start = datetime(2026, 11, 20, 7, 30, tzinfo=timezone.utc)
        for server_tz in ("UTC", "America/Los_Angeles", "Asia/Tokyo"):
            monkeypatch.setenv("TZ", server_tz)
            time.tzset()
            assert is_open(CAFE, start, 30, CAPE_TOWN) is True
        monkeypatch.delenv("TZ")
        time.tzset()

    def test_local_start_is_in_the_city(self):
        start = local_start(FRIDAY, "07:30 PM", CAPE_TOWN)
        assert start.utcoffset().total_seconds() == 2 * 3600
        assert (start.hour, start.minute) == (19, 30)
        assert local_start(FRIDAY, "19:30", CAPE_TOWN) == start
        with pytest.raises(ValueError):
            local_start(FRIDAY, "evening", CAPE_TOWN)

    def test_daylight_saving_is_the_citys(self):
        # London is on GMT in November and BST in July: 08:30 UTC is 08:30 then 09:30.
        winter = datetime(2026, 11, 20, 8, 30, tzinfo=timezone.utc)
        summer = datetime(2026, 7, 17, 7, 30, tzinfo=timezone.utc)  # a Friday
        assert is_open(CAFE, winter, 30, LONDON) is True
        assert is_open(CAFE, summer, 30, LONDON) is True
        assert is_open(CAFE, datetime(2026, 7, 17, 6, 30, tzinfo=timezone.utc), 30, LONDON) is False


class TestRules:
    START = at(21, 10)  # Saturday morning: the cafe is closed

    def test_an_open_place_is_kept(self):
        place = {"name": "Truth Coffee", "hours": CAFE}
        decision = decide_for_slot(place, [], at(20, 10), 60, CAPE_TOWN)
        assert (decision.action, decision.place, decision.note) == ("keep", place, None)

    def test_a_closed_place_is_swapped_for_an_open_one_for_the_same_slot(self):
        closed = {"name": "Truth Coffee", "hours": CAFE}
        also_closed = {"name": "Weekday Cafe", "hours": CAFE}
        open_now = {"name": "Always Open Diner", "hours": ALWAYS}
        decision = decide_for_slot(closed, [also_closed, open_now], self.START, 60, CAPE_TOWN)
        assert (decision.action, decision.place, decision.note) == ("swap", open_now, None)

    def test_a_confirmed_open_alternative_beats_one_with_unknown_hours(self):
        unknown = {"name": "Mystery Cafe", "hours": None}
        open_now = {"name": "Always Open Diner", "hours": ALWAYS}
        decision = decide_for_slot({"hours": CAFE}, [unknown, open_now], self.START, 60, CAPE_TOWN)
        assert decision.place is open_now

    def test_an_alternative_with_unknown_hours_is_used_marked_not_confirmed(self):
        unknown = {"name": "Mystery Cafe", "hours": None}
        decision = decide_for_slot({"hours": CAFE}, [{"hours": CAFE}, unknown], self.START, 60, CAPE_TOWN)
        assert (decision.action, decision.place, decision.note) == ("swap", unknown, HOURS_NOT_CONFIRMED)

    def test_no_open_place_for_the_slot_drops_the_stop_and_says_why(self):
        closed = {"name": "Truth Coffee", "hours": CAFE}
        decision = decide_for_slot(closed, [{"name": "Other", "hours": CAFE}], self.START, 60, CAPE_TOWN)
        assert decision.action == "drop"
        assert decision.place is None
        assert decision.note == "Truth Coffee is closed at 10:00 on Saturday, and no other place for this Slot is open then."

    def test_a_place_without_hours_is_kept_marked_not_confirmed(self):
        place = {"name": "Kalk Bay Harbour", "hours": None}
        decision = decide_for_slot(place, [{"hours": ALWAYS}], self.START, 60, CAPE_TOWN)
        assert (decision.action, decision.place, decision.note) == ("keep_unconfirmed", place, HOURS_NOT_CONFIRMED)

