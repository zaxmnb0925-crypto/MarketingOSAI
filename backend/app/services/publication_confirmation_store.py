import hashlib
import json
from typing import Any

from app.core.redis_client import redis_client


PUBLICATION_CONFIRMATION_REDIS_PREFIX = (
    "publication_publish_confirmation:"
)


def _key(
    confirmation_value: str,
) -> str:
    #
    # Never place the bearer confirmation itself in
    # Redis keyspace. Only a deterministic SHA-256
    # digest is used for lookup.
    #
    digest = hashlib.sha256(
        confirmation_value.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        PUBLICATION_CONFIRMATION_REDIS_PREFIX
        + digest
    )


async def register_publication_confirmation(
    confirmation_value: str,
    payload: dict[str, Any],
    ttl_seconds: int,
) -> None:
    if not confirmation_value:
        raise ValueError(
            "Publication confirmation cannot be empty"
        )

    if not payload:
        raise ValueError(
            "Publication confirmation payload "
            "cannot be empty"
        )

    if ttl_seconds <= 0:
        raise ValueError(
            "Publication confirmation TTL "
            "must be positive"
        )

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )

    created = await redis_client.set(
        _key(confirmation_value),
        serialized,
        ex=ttl_seconds,
        nx=True,
    )

    if not created:
        raise RuntimeError(
            "Publication confirmation "
            "already registered"
        )


async def consume_publication_confirmation(
    confirmation_value: str,
) -> dict[str, Any] | None:
    if not confirmation_value:
        return None

    serialized = await redis_client.getdel(
        _key(confirmation_value)
    )

    if serialized is None:
        return None

    try:
        payload = json.loads(
            serialized
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Stored publication confirmation "
            "payload is invalid"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Stored publication confirmation "
            "payload is invalid"
        )

    return payload
