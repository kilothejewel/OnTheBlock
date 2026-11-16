"""
Guests (#125): using the app without an account.

- `create_guest` makes a guest user (no personal data), at most
  OTB_GUEST_SESSIONS_PER_IP_DAY a day per IP, and lazily removes up to 100
  guests idle for OTB_GUEST_IDLE_DAYS.
- `take_guest_plan` applies the guest Plan limits on top of each user's
  own daily quota (#43): per IP, and a cap for all guests together.
- `claim_guest` keeps a guest's work when they sign up (the row becomes the
  account) or log in (their chats and today's Plan counts move to the account).

Per-IP counts live in the quota guard's table (#121) under a keyed hash of
the IP, never the IP itself.
"""

import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import Chat
from app.models.plan_quota import PlanQuotaUsage
from app.models.user import User
from app.services.quota import Quota, quota as app_quota


def ip_key(ip: Optional[str]) -> str:
    """A short keyed hash of the client IP: enough to count, not enough to recover it."""
    digest = hmac.new(settings.SECRET_KEY.encode(), (ip or "unknown").encode(), hashlib.sha256).hexdigest()
    return digest[:16]


def _counter() -> Quota:
    """The guest counters, with limits read from settings each time (tests change them)."""
    return Quota(app_quota.bind, limits={
        "guests.sessions_ip.*": {"day": settings.GUEST_SESSIONS_PER_IP_DAY},
        "guests.plans_ip.*": {"day": settings.GUEST_PLANS_PER_IP_DAY},
        "guests.plans_all": {"day": settings.GUEST_PLANS_DAY_CAP},
    }, pool_caps={}, clock=app_quota.clock)


def remove_idle_guests(db: Session, now: Optional[datetime] = None, limit: int = 100) -> int:
    """Delete up to `limit` guests not seen for OTB_GUEST_IDLE_DAYS (their chats go with them)."""
    cutoff = (now or datetime.utcnow()) - timedelta(days=settings.GUEST_IDLE_DAYS)
    idle = (
        db.query(User)
        .filter(User.is_guest.is_(True), func.coalesce(User.last_seen_at, User.created_at) < cutoff)
        .limit(limit)
        .all()
    )
    for user in idle:
        db.delete(user)
    db.commit()
    return len(idle)


def create_guest(db: Session, ip: Optional[str], now: Optional[datetime] = None) -> Optional[User]:
    """A new guest user, or None when this IP has made too many today."""
    remove_idle_guests(db, now)
    if not _counter().take(f"guests.sessions_ip.{ip_key(ip)}", pool="guests"):
        return None
    user = User(is_guest=True, last_seen_at=now or datetime.utcnow())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def take_guest_plan(ip: Optional[str]) -> Optional[str]:
    """
    The guest limits beyond the user's own quota. None when the Plan may go
    ahead, else which limit was hit: "ip" or "all_guests".
    """
    counter = _counter()
    if not counter.take(f"guests.plans_ip.{ip_key(ip)}", pool="guests"):
        return "ip"
    if not counter.take("guests.plans_all", pool="guests"):
        return "all_guests"
    return None


def _move_plan_counts(db: Session, guest: User, account: User) -> None:
    """Add the guest's Plan counts to the account's, so logging in can't reset a quota."""
    for row in db.query(PlanQuotaUsage).filter(PlanQuotaUsage.user_id == guest.id).all():
        mine = db.query(PlanQuotaUsage).filter_by(user_id=account.id, day=row.day).first()
        if mine:
            mine.used += row.used
        else:
            db.add(PlanQuotaUsage(user_id=account.id, day=row.day, used=row.used))
        db.delete(row)


def claim_by_login(db: Session, guest: User, account: User) -> int:
    """Move the guest's chats and today's Plan counts to the account, then delete the guest. Returns chats moved."""
    chats = db.query(Chat).filter(Chat.user_id == guest.id).all()
    for chat in chats:
        chat.user_id = account.id
    db.flush()
    _move_plan_counts(db, guest, account)
    db.flush()
    db.expire(guest)
    db.delete(db.get(User, guest.id))
    db.commit()
    return len(chats)


def claim_by_register(db: Session, guest: User, *, username: str, email: str, hashed_password: str) -> int:
    """Turn the guest row into the account in place: same user id, so its chats stay. Returns chats kept."""
    guest.username, guest.email, guest.hashed_password = username, email, hashed_password
    guest.is_guest = False
    db.commit()
    db.refresh(guest)
    return db.query(Chat).filter(Chat.user_id == guest.id).count()


def find_account(db: Session, identifier: str) -> Optional[User]:
    return (
        db.query(User)
        .filter(User.is_guest.is_(False), or_(User.email == identifier, User.username == identifier))
        .first()
    )
