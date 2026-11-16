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


def user_id_from_token(token: str) -> Optional[int]:
    """The user id in a valid, unexpired access token, or None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that resolves the current user from a bearer JWT.

    Decodes and verifies the token signature, reads the ``sub`` claim (the user id),
    loads that user from the database, and raises 401 on any failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = user_id_from_token(credentials.credentials)
    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user
