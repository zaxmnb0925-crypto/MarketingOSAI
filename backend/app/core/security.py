import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()

ACCESS_TOKEN_MINUTES = 30
REFRESH_TOKEN_DAYS = 30
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: UUID) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ACCESS_TOKEN_MINUTES)

    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": expires,
    }

    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm=JWT_ALGORITHM,
    )

    return token, ACCESS_TOKEN_MINUTES * 60


def decode_access_token(token: str) -> UUID:
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[JWT_ALGORITHM],
    )

    if payload.get("type") != "access":
        raise ValueError("Invalid token type")

    subject = payload.get("sub")

    if not subject:
        raise ValueError("Missing token subject")

    return UUID(subject)


def create_refresh_token() -> tuple[str, str, datetime]:
    raw_token = secrets.token_urlsafe(48)

    token_digest = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_DAYS
    )

    return raw_token, token_digest, expires_at


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()
