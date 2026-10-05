"""
Password hashing and JWT token creation/verification.

Design notes:
- Passwords are hashed with bcrypt via passlib. Never store or log plaintext.
- Access tokens are short-lived; refresh tokens are longer-lived and carry a
  distinct `type` claim so an access token can never be replayed as a refresh
  token (and vice versa).
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: Literal["access", "refresh"], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: UUID) -> str:
    return _create_token(str(user_id), "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: UUID) -> str:
    return _create_token(str(user_id), "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> str:
    """Returns the user_id (sub claim) if valid, else raises InvalidTokenError."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise InvalidTokenError("Token is invalid or expired")

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type} token")

    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token missing subject")
    return sub
