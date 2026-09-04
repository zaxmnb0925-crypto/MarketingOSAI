from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException, status
from redis.exceptions import RedisError


_RATE_LIMIT_LUA = """
local current = redis.call("INCR", KEYS[1])
local ttl = redis.call("TTL", KEYS[1])

if current == 1 or ttl < 0 then
    redis.call("EXPIRE", KEYS[1], ARGV[2])
    ttl = tonumber(ARGV[2])
end

return {current, ttl}
"""


def normalized_login_identifier_hash(identifier: object) -> str:
    normalized = unicodedata.normalize(
        "NFKC",
        str(identifier),
    ).strip().casefold()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def _rate_limit_key(
    scope: str,
    identifiers: Sequence[object],
) -> str:
    material = "\x1f".join(
        (
            scope,
            *(
                str(value)
                for value in identifiers
            ),
        )
    )

    digest = hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()

    return (
        "marketingos:rate-limit:"
        + scope
        + ":"
        + digest
    )


async def enforce_rate_limit(
    *,
    scope: str,
    identifiers: Sequence[object],
    limit: int,
    window_seconds: int,
    client: Any | None = None,
) -> None:
    if not scope:
        raise ValueError(
            "rate-limit scope is required"
        )

    if not identifiers:
        raise ValueError(
            "rate-limit identifiers are required"
        )

    if limit <= 0:
        raise ValueError(
            "rate-limit limit must be positive"
        )

    if window_seconds <= 0:
        raise ValueError(
            "rate-limit window must be positive"
        )

    if client is None:
        from app.core.redis_client import (
            redis_client,
        )

        client = redis_client

    key = _rate_limit_key(
        scope,
        identifiers,
    )

    try:
        result = await client.eval(
            _RATE_LIMIT_LUA,
            1,
            key,
            limit,
            window_seconds,
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit service unavailable",
        ) from exc

    try:
        current = int(result[0])
        ttl = int(result[1])
    except (
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit service unavailable",
        ) from exc

    if current <= limit:
        return

    retry_after = max(
        ttl,
        1,
    )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests",
        headers={
            "Retry-After":
                str(retry_after),
        },
    )
