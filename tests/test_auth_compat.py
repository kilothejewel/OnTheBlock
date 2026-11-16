"""
Sign-ins made before the auth libraries changed (passlib + python-jose, #22)
keep working. The hash and tokens below were made by that code with the test
secret, and are hard-coded so the old libraries aren't needed to check them.
"""

import bcrypt
import pytest

from app.core.security import get_password_hash, verify_password
from app.models.user import User

# passlib's bcrypt hash of "supersecret123".
PASSLIB_HASH = "$2b$12$s9HwCp6fFiHhQG3hSyfJsO7CvOM7HUgl3L9GSgj9Yyypz58lYc6sq"
# passlib's bcrypt hash of "p" * 100; passlib hashed only the first 72 bytes.
PASSLIB_LONG_HASH = "$2b$12$xFeDJj24XOFGik5M.T3WwuW2192OR6NT8jM7bcxA5.x7m/75CgYjO"
# python-jose HS256 tokens for user 1: one valid for 50 years, one already expired.
JOSE_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjozMzcxNjE4NTQzfQ."
    "Fyc9yJaU4iG6hy-ZlOePyN_FE0BWWqhUMNfUPVtdqVU"
)
EXPIRED_JOSE_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzk0ODE4NDgzfQ."
    "UsfhTyQUHHZ8Kqz0GwoAzUjiGbNjJwANK7LMPY_kBJg"
)


@pytest.fixture
def existing_user(db_session):
    """A user who registered before the change, with id 1 as in the tokens."""
    user = User(id=1, username="sam", email="sam@example.com", hashed_password=PASSLIB_HASH)
    db_session.add(user)
    db_session.commit()
    return user


def test_an_existing_user_can_still_log_in(client, existing_user):
    resp = client.post("/api/v1/auth/login", json={"identifier": "sam", "password": "supersecret123"})
    assert resp.status_code == 200, resp.text

    wrong = client.post("/api/v1/auth/login", json={"identifier": "sam", "password": "supersecret124"})
    assert wrong.status_code == 401


def test_a_token_issued_before_the_change_still_works(client, existing_user):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {JOSE_TOKEN}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["username"] == "sam"


def test_an_expired_token_from_before_the_change_is_refused(client, existing_user):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {EXPIRED_JOSE_TOKEN}"})
    assert resp.status_code == 401


def test_long_passwords_check_the_first_72_bytes_as_before():
    """bcrypt only uses 72 bytes; passlib cut longer passwords there, and so do we."""
    assert verify_password("p" * 100, PASSLIB_LONG_HASH)
    assert verify_password("p" * 72, PASSLIB_LONG_HASH)
    assert verify_password("p" * 128, get_password_hash("p" * 100))


def test_new_hashes_are_bcrypt_with_a_salt():
    first, second = get_password_hash("supersecret123"), get_password_hash("supersecret123")
    assert first.startswith("$2b$12$")
    assert first != second
    assert bcrypt.checkpw(b"supersecret123", first.encode())


def test_a_malformed_stored_hash_never_logs_anyone_in():
    assert verify_password("supersecret123", "not-a-bcrypt-hash") is False
    assert verify_password("supersecret123", "") is False
