import hashlib
import json
from typing import Any

from app.core.redis_client import redis_client


PUBLICATION_ACTIVATION_REDIS_PREFIX = (
    "publication_publish_activation:"
)


def _key(
    activation_value: str,
) -> str:
    #
    # The opaque bearer must never appear directly in
    # Redis keyspace.
    #
    digest = hashlib.sha256(
        activation_value.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        PUBLICATION_ACTIVATION_REDIS_PREFIX
        + digest
    )


async def register_publication_activation(
    activation_value: str,
    payload: dict[str, Any],
    ttl_seconds: int,
) -> None:
    if not activation_value:
        raise ValueError(
            "Publication activation cannot be empty"
        )

    if not payload:
        raise ValueError(
            "Publication activation payload cannot be empty"
        )

    if ttl_seconds <= 0:
        raise ValueError(
            "Publication activation TTL must be positive"
        )

    serialized = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )

    created = await redis_client.set(
        _key(
            activation_value
        ),
        serialized,
        ex=ttl_seconds,
        nx=True,
    )

    if not created:
        raise RuntimeError(
            "Publication activation already registered"
        )


async def consume_publication_activation(
    activation_value: str,
) -> dict[str, Any] | None:
    if not activation_value:
        return None

    serialized = await redis_client.getdel(
        _key(
            activation_value
        )
    )

    if serialized is None:
        return None

    try:
        payload = json.loads(
            serialized
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Stored publication activation payload "
            "is invalid"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "Stored publication activation payload "
            "is invalid"
        )

    return payload
