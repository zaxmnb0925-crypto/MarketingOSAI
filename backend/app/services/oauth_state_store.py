import json
from typing import Any

from app.core.redis_client import redis_client


OAUTH_STATE_REDIS_PREFIX = "oauth_state_nonce:"
OAUTH_STATE_V2_REDIS_PREFIX = "oauth_state_v2:"


def _key(nonce: str) -> str:
    return (
        OAUTH_STATE_REDIS_PREFIX
        + nonce
    )


def _v2_key(state_value: str) -> str:
    return (
        OAUTH_STATE_V2_REDIS_PREFIX
        + state_value
    )


async def register_oauth_nonce(
    nonce: str,
    ttl_seconds: int,
) -> None:
    if not nonce:
        raise ValueError(
            "OAuth nonce cannot be empty"
        )

    created = await redis_client.set(
        _key(nonce),
        "1",
        ex=ttl_seconds,
        nx=True,
    )

    if not created:
        raise RuntimeError(
            "OAuth nonce already registered"
        )


async def consume_oauth_nonce(
    nonce: str,
) -> bool:
    if not nonce:
        return False

    key = _key(nonce)

    value = await redis_client.getdel(
        key
    )

    return value is not None


async def register_oauth_state_v2(
    state_value: str,
    payload: dict[str, Any],
    ttl_seconds: int,
) -> None:
    if not state_value:
        raise ValueError(
            "OAuth state cannot be empty"
        )

    if not payload:
        raise ValueError(
            "OAuth state payload cannot be empty"
        )

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )

    created = await redis_client.set(
        _v2_key(state_value),
        serialized,
        ex=ttl_seconds,
        nx=True,
    )

    if not created:
        raise RuntimeError(
            "OAuth state already registered"
        )


async def consume_oauth_state_v2(
    state_value: str,
) -> dict[str, Any] | None:
    if not state_value:
        return None

    serialized = await redis_client.getdel(
        _v2_key(state_value)
    )

    if serialized is None:
        return None

    try:
        payload = json.loads(
            serialized
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Stored OAuth state payload is invalid"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Stored OAuth state payload is invalid"
        )

    return payload
