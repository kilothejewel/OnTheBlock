from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.http_client import get_http_client
from app.core.security import (
    create_access_token,
    create_guest_token,
    get_actor,
    get_password_hash,
    optional_actor,
    verify_password,
)
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services import guests

router = APIRouter(prefix="/auth", tags=["auth"])

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _issue_token(user: User, claimed_chats: int = 0) -> Token:
    """Mint a bearer token whose subject is the user's id."""
    return Token(access_token=create_access_token(data={"sub": str(user.id)}), claimed_chats=claimed_chats)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db), actor: Optional[User] = Depends(optional_actor)) -> Token:
    """
    Register a new user. Enforces unique email + username, stores a bcrypt hash of
    the password, and returns a JWT immediately (auto-login on register).

    Sent with a guest token, the guest becomes the account in place (same user
    id), so everything they made as a guest stays theirs; `claimed_chats` says how many chats.
    """
    existing = (
        db.query(User)
        .filter((User.email == payload.email) | (User.username == payload.username))
        .first()
    )
    if existing is not None:
        conflict = "email" if existing.email == payload.email else "username"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this {conflict} already exists",
        )

    hashed = get_password_hash(payload.password)
    if actor is not None and actor.is_guest:
        claimed = guests.claim_by_register(db, actor, username=payload.username, email=payload.email, hashed_password=hashed)
        return _issue_token(actor, claimed)

    user = User(username=payload.username, email=payload.email, hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_token(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db), actor: Optional[User] = Depends(optional_actor)) -> Token:
    """
    Verify credentials (email or username + password) and return a JWT. Sent
    with a guest token, the guest's chats and today's Plan counts move to the
    account and the guest is removed.
    """
    user = guests.find_account(db, payload.identifier)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
        )
    claimed = 0
    if actor is not None and actor.is_guest:
        claimed = guests.claim_by_login(db, actor, user)
    return _issue_token(user, claimed)


class GuestRequest(BaseModel):
    turnstile_token: Optional[str] = None  # needed only when OTB_TURNSTILE_SECRET is set


async def _turnstile_ok(token: Optional[str], ip: Optional[str]) -> bool:
    if not settings.TURNSTILE_SECRET:
        return True
    if not token:
        return False
    try:
        response = await get_http_client().post(
            TURNSTILE_VERIFY_URL, data={"secret": settings.TURNSTILE_SECRET, "response": token, "remoteip": ip or ""}
        )
        return bool(response.json().get("success"))
    except Exception:
        return False


@router.post("/guest", response_model=Token, status_code=status.HTTP_201_CREATED)
async def create_guest_session(request: Request, body: Optional[GuestRequest] = None, db: Session = Depends(get_db)) -> Token:
    """
    Start using the app without an account: a guest session with no email,
    name or password (#125). The token lasts 30 days. At most
    OTB_GUEST_SESSIONS_PER_IP_DAY new guests a day per IP.
    """
    ip = request.client.host if request.client else None
    if not await _turnstile_ok(body.turnstile_token if body else None, ip):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please complete the check and try again.")
    guest = guests.create_guest(db, ip)
    if guest is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many guest sessions from your network today. Create a free account to keep going.",
        )
    return Token(access_token=create_guest_token(guest.id), is_guest=True)


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_actor)) -> User:
    """Return the signed-in user's profile, or a guest's (no email or username)."""
    return current_user
