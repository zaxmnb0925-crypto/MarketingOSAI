import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.services.oauth_state_store import (
    consume_oauth_nonce,
    consume_oauth_state_v2,
    register_oauth_nonce,
    register_oauth_state_v2,
)


OAUTH_STATE_TTL_SECONDS = 600


class OAuthStateError(RuntimeError):
    pass


class OAuthStateExpired(OAuthStateError):
    pass


class OAuthStateInvalid(OAuthStateError):
    pass


class OAuthStateReplay(OAuthStateError):
    pass


@dataclass(frozen=True)
class OAuthStatePayload:
    workspace_id: UUID
    provider: str
    nonce: str
    issued_at: int


def _sign(payload: bytes) -> str:
    digest = hmac.new(
        settings.secret_key.encode(),
        payload,
        hashlib.sha256,
    ).digest()

    return base64.urlsafe_b64encode(
        digest
    ).decode().rstrip("=")


def _encode_payload(data: dict) -> str:
    raw = json.dumps(
        data,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()

    return base64.urlsafe_b64encode(
        raw
    ).decode().rstrip("=")


def _decode_payload(value: str) -> bytes:
    padding = "=" * (
        (4 - len(value) % 4) % 4
    )

    try:
        return base64.urlsafe_b64decode(
            value + padding
        )
    except Exception as exc:
        raise OAuthStateInvalid(
            "Invalid OAuth state encoding"
        ) from exc


def _verify_signature_and_payload(
    state: str,
    expected_provider: str | None = None,
) -> OAuthStatePayload:
    try:
        encoded, signature = state.split(
            ".",
            1,
        )
    except ValueError as exc:
        raise OAuthStateInvalid(
            "Malformed OAuth state"
        ) from exc

    expected_signature = _sign(
        encoded.encode()
    )

    if not hmac.compare_digest(
        signature,
        expected_signature,
    ):
        raise OAuthStateInvalid(
            "OAuth state signature invalid"
        )

    raw = _decode_payload(
        encoded
    )

    try:
        data = json.loads(
            raw.decode()
        )

        workspace_id = UUID(
            data["workspace_id"]
        )

        provider = str(
            data["provider"]
        )

        nonce = str(
            data["nonce"]
        )

        issued_at = int(
            data["issued_at"]
        )
    except Exception as exc:
        raise OAuthStateInvalid(
            "OAuth state payload invalid"
        ) from exc

    now = int(time.time())

    if issued_at > now + 30:
        raise OAuthStateInvalid(
            "OAuth state issued_at invalid"
        )

    if (
        now - issued_at
        > OAUTH_STATE_TTL_SECONDS
    ):
        raise OAuthStateExpired(
            "OAuth state expired"
        )

    if (
        expected_provider is not None
        and provider != expected_provider
    ):
        raise OAuthStateInvalid(
            "OAuth provider mismatch"
        )

    return OAuthStatePayload(
        workspace_id=workspace_id,
        provider=provider,
        nonce=nonce,
        issued_at=issued_at,
    )


async def create_oauth_state(
    workspace_id: UUID,
    provider: str,
) -> str:
    now = int(time.time())

    nonce = secrets.token_urlsafe(24)

    data = {
        "workspace_id": str(workspace_id),
        "provider": provider,
        "nonce": nonce,
        "issued_at": now,
    }

    encoded = _encode_payload(data)

    signature = _sign(
        encoded.encode()
    )

    await register_oauth_nonce(
        nonce,
        ttl_seconds=OAUTH_STATE_TTL_SECONDS,
    )

    return f"{encoded}.{signature}"


async def consume_and_verify_oauth_state(
    state: str,
    expected_provider: str | None = None,
) -> OAuthStatePayload:
    payload = _verify_signature_and_payload(
        state,
        expected_provider=expected_provider,
    )

    consumed = await consume_oauth_nonce(
        payload.nonce
    )

    if not consumed:
        raise OAuthStateReplay(
            "OAuth state already used or expired"
        )

    return payload


@dataclass(frozen=True)
class OAuthStatePayloadV2:
    workspace_id: UUID
    provider: str
    user_id: UUID
    issued_at: int


async def create_oauth_state_v2(
    workspace_id: UUID,
    provider: str,
    user_id: UUID,
) -> str:
    if not provider:
        raise OAuthStateInvalid(
            "OAuth provider cannot be empty"
        )

    now = int(time.time())

    # 256 bits of cryptographically secure entropy.
    # token_urlsafe(32) produces approximately
    # 43 URL-safe characters.
    state_value = secrets.token_urlsafe(32)

    payload = {
        "workspace_id": str(workspace_id),
        "provider": provider,
        "user_id": str(user_id),
        "issued_at": now,
    }

    await register_oauth_state_v2(
        state_value,
        payload,
        ttl_seconds=OAUTH_STATE_TTL_SECONDS,
    )

    return state_value


async def consume_and_verify_oauth_state_v2(
    state_value: str,
    expected_provider: str | None = None,
) -> OAuthStatePayloadV2:
    if not state_value:
        raise OAuthStateInvalid(
            "OAuth state is missing"
        )

    data = await consume_oauth_state_v2(
        state_value
    )

    if data is None:
        raise OAuthStateReplay(
            "OAuth state already used or expired"
        )

    try:
        workspace_id = UUID(
            str(data["workspace_id"])
        )

        provider = str(
            data["provider"]
        )

        user_id = UUID(
            str(data["user_id"])
        )

        issued_at = int(
            data["issued_at"]
        )

    except Exception as exc:
        raise OAuthStateInvalid(
            "OAuth state payload invalid"
        ) from exc

    now = int(time.time())

    if issued_at > now + 30:
        raise OAuthStateInvalid(
            "OAuth state issued_at invalid"
        )

    if (
        now - issued_at
        > OAUTH_STATE_TTL_SECONDS
    ):
        raise OAuthStateExpired(
            "OAuth state expired"
        )

    if (
        expected_provider is not None
        and provider != expected_provider
    ):
        raise OAuthStateInvalid(
            "OAuth provider mismatch"
        )

    return OAuthStatePayloadV2(
        workspace_id=workspace_id,
        provider=provider,
        user_id=user_id,
        issued_at=issued_at,
    )

