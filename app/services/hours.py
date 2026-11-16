"""
Opening hours: is a place open for a Stop's whole visit?

Hours come from Google's live check (#93) as `regularOpeningHours`, whose
`periods` are in the place's local time, which for us is the city's time zone
(`City.timezone`). Everything here is computed in that zone, never the
server's, so a Plan for Cape Town checks Cape Town's clock wherever the API
runs. Pure code: no network, no database.

The validator (#99) applies the rules with `decide_for_slot`:
- the Stop's place is closed at its time: swap in another open place for the Slot
- no place for the Slot is open: drop the Stop and say why
- Google has no hours for the place: keep the Stop, marked "hours not confirmed"
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence
from zoneinfo import ZoneInfo

MINUTES_PER_DAY = 24 * 60
MINUTES_PER_WEEK = 7 * MINUTES_PER_DAY

HOURS_NOT_CONFIRMED = "hours not confirmed"

Hours = Optional[Dict[str, Any]]  # Google's regularOpeningHours, or None when Google has none


def _week_minute(point: Dict[str, Any]) -> int:
    """Minutes since Sunday 00:00 for a Google period point ({day: 0=Sunday..6, hour, minute})."""
    return int(point.get("day", 0)) * MINUTES_PER_DAY + int(point.get("hour", 0)) * 60 + int(point.get("minute", 0))


def _open_intervals(periods: Sequence[Dict[str, Any]]) -> Optional[List[tuple]]:
    """
    The week's open intervals as (start, end) minutes since Sunday 00:00, with
    `end` past the end of the week for periods that wrap (Saturday night into
    Sunday). None means open all the time: Google sends one period with no close.
    """
    intervals = []
    for period in periods:
        opens = period.get("open")
        if not opens:
            continue
        closes = period.get("close")
        if not closes:
            return None  # open 24 hours, every day
        start, end = _week_minute(opens), _week_minute(closes)
        if end <= start:
            end += MINUTES_PER_WEEK  # overnight across the week boundary
        intervals.append((start, end))
    return intervals


def is_open(hours: Hours, start: datetime, minutes: int, tz: str) -> Optional[bool]:
    """
    Whether the place is open for the whole visit: from `start` for `minutes`.

    `start` is the Stop's start; a naive datetime is read as the city's local
    time (`tz`, e.g. "Africa/Johannesburg"), an aware one is converted to it.
    Returns None when the hours are unknown (no hours, or no periods), True
    when one open period covers the whole visit, and False otherwise,
    including on a day the place has no period at all.
    """
    if not hours:
        return None
    periods = hours.get("periods") or []
    if not periods:
        return None

    intervals = _open_intervals(periods)
    if intervals is None:
        return True
    if not intervals:
        return None

    zone = ZoneInfo(tz)
    local = start.replace(tzinfo=zone) if start.tzinfo is None else start.astimezone(zone)
    google_day = (local.weekday() + 1) % 7  # Python: Monday=0; Google: Sunday=0
    visit_start = google_day * MINUTES_PER_DAY + local.hour * 60 + local.minute
    visit_end = visit_start + max(int(minutes), 0)

    for open_at, close_at in intervals:
        # The same period last week covers early-Sunday visits after a Saturday night opening.
        for shift in (0, -MINUTES_PER_WEEK, MINUTES_PER_WEEK):
            # Half-open: arriving exactly at closing time is too late.
            if open_at + shift <= visit_start < close_at + shift and visit_end <= close_at + shift:
                return True
    return False


def local_start(day: datetime, time_of_day: str, tz: str) -> datetime:
    """The Stop's start as an aware datetime in the city: `day`'s date at "HH:MM AM/PM" or "HH:MM"."""
    text = time_of_day.strip().upper()
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Unrecognised time {time_of_day!r}")
    return datetime(day.year, day.month, day.day, parsed.hour, parsed.minute, tzinfo=ZoneInfo(tz))


@dataclass(frozen=True)
class HoursDecision:
    """What to do with a Stop given its place's hours."""

    action: Literal["keep", "keep_unconfirmed", "swap", "drop"]
    place: Optional[Dict[str, Any]]  # the place to use; None when dropped
    note: Optional[str] = None  # shown to the user: "hours not confirmed" or why it was dropped


def decide_for_slot(
    place: Dict[str, Any],
    alternatives: Sequence[Dict[str, Any]],
    start: datetime,
    minutes: int,
    tz: str,
) -> HoursDecision:
    """
    Apply the opening-hours rules to one Stop.

    Each place is a dict with its live `hours` (regularOpeningHours, or None).
    Open → keep it. No hours → keep it, marked "hours not confirmed". Closed →
    the first alternative that's open (one with unknown hours only if none is
    confirmed open), or drop the Stop with the reason.
    """
    status = is_open(place.get("hours"), start, minutes, tz)
    if status is True:
        return HoursDecision("keep", place)
    if status is None:
        return HoursDecision("keep_unconfirmed", place, HOURS_NOT_CONFIRMED)

    unconfirmed = None
    for alternative in alternatives:
        alt_status = is_open(alternative.get("hours"), start, minutes, tz)
        if alt_status is True:
            return HoursDecision("swap", alternative)
        if alt_status is None and unconfirmed is None:
            unconfirmed = alternative
    if unconfirmed is not None:
        return HoursDecision("swap", unconfirmed, HOURS_NOT_CONFIRMED)

    name = place.get("name") or "This place"
    when = start.astimezone(ZoneInfo(tz)) if start.tzinfo else start
    return HoursDecision(
        "drop", None,
        f"{name} is closed at {when.strftime('%H:%M')} on {when.strftime('%A')}, and no other place for this Slot is open then.",
    )

