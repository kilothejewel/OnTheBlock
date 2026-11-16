from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer()

# bcrypt only reads the first 72 bytes of a password. passlib, which made the
# hashes stored before #22, cut longer ones there silently; bcrypt 5 refuses
# them, so cut them the same way to keep those hashes verifying.
BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt (cost 12, as passlib used)."""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash. A malformed hash never matches."""
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token from the given claims."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


GUEST_TOKEN_DAYS = 30
GUEST_TOKEN_TYPE = "guest"


def create_guest_token(user_id: int) -> str:
    """A guest session's token: typ "guest", valid for 30 days (#125)."""
    return create_access_token({"sub": str(user_id), "typ": GUEST_TOKEN_TYPE}, expires_delta=timedelta(days=GUEST_TOKEN_DAYS))


def token_claims(token: str) -> Optional[dict]:
    """The claims of a valid, unexpired token, or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        int(payload["sub"])
        return payload
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None


def user_id_from_token(token: str) -> Optional[int]:
    """The user id in a valid, unexpired access token, or None."""
    claims = token_claims(token)
    return int(claims["sub"]) if claims else None


class AccountRequired(Exception):
    """A guest tried something only an account can do (#125)."""


ACCOUNT_REQUIRED_BODY = {"code": "account_required", "message": "Create a free account to save this."}

_bearer_optional = HTTPBearer(auto_error=False)
_SEEN_EVERY = timedelta(hours=1)


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def resolve_token(token: str, db: Session) -> Optional[User]:
    """
    The user a token belongs to, or None. A guest token only works for a row
    that is still a guest: once the guest signs up or logs in, it's claimed and
    stops working.
    """
    claims = token_claims(token)
    if claims is None:
        return None
    user = db.query(User).filter(User.id == int(claims["sub"])).first()
    if user is None:
        return None
    is_guest_token = claims.get("typ") == GUEST_TOKEN_TYPE
    if is_guest_token != bool(user.is_guest):
        return None
    return user


def _touch(db: Session, user: User) -> None:
    now = datetime.utcnow()
    if user.last_seen_at is None or now - user.last_seen_at > _SEEN_EVERY:
        user.last_seen_at = now
        db.commit()


async def get_actor(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """An account or a guest (#125): for the chat, place details, feedback and planning."""
    user = resolve_token(credentials.credentials, db)
    if user is None:
        raise _credentials_error()
    if user.is_guest:
        _touch(db, user)
    return user


async def require_account(actor: User = Depends(get_actor)) -> User:
    """Accounts only: Trips, Saved places and account routes. A guest gets 401 account_required."""
    if actor.is_guest:
        raise AccountRequired()
    return actor


async def optional_actor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """The actor when a valid token is sent, else None (sign-up and log-in claim a guest)."""
    if credentials is None:
        return None
    return resolve_token(credentials.credentials, db)


# Routes written before guests existed use this name; it means "accounts only".
get_current_user = require_account
