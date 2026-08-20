import asyncio
import hashlib
from pathlib import Path

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError

from app.core.rate_limit import (
    enforce_rate_limit,
    normalized_login_identifier_hash,
)


ROOT = Path(__file__).resolve().parents[2]


class FakeRedis:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    async def eval(
        self,
        script,
        numkeys,
        key,
        limit,
        window_seconds,
    ):
        self.calls.append(
            (
                script,
                numkeys,
                key,
                limit,
                window_seconds,
            )
        )

        if self.error is not None:
            raise self.error

        return self.result


def run(coro):
    return asyncio.run(coro)


def test_login_identifier_hash_is_normalized_and_non_pii():
    first = normalized_login_identifier_hash(
        "  User@Example.COM "
    )

    second = normalized_login_identifier_hash(
        "user@example.com"
    )

    assert first == second
    assert len(first) == 64

    int(
        first,
        16,
    )

    assert "user@example.com" not in first


def test_rate_limit_uses_atomic_lua_and_allows_at_limit():
    redis = FakeRedis(
        result=[
            10,
            42,
        ]
    )

    run(
        enforce_rate_limit(
            scope="login",
            identifiers=(
                normalized_login_identifier_hash(
                    "user@example.com"
                ),
            ),
            limit=10,
            window_seconds=600,
            client=redis,
        )
    )

    assert len(redis.calls) == 1

    (
        script,
        numkeys,
        key,
        limit,
        window,
    ) = redis.calls[0]

    assert 'redis.call("INCR"' in script
    assert 'redis.call("EXPIRE"' in script
    assert 'redis.call("TTL"' in script

    assert numkeys == 1
    assert limit == 10
    assert window == 600

    assert key.startswith(
        "marketingos:rate-limit:login:"
    )

    assert "user@example.com" not in key


def test_rate_limit_returns_429_and_retry_after():
    redis = FakeRedis(
        result=[
            11,
            37,
        ]
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        run(
            enforce_rate_limit(
                scope="ai_generation",
                identifiers=(
                    "user-id",
                    "workspace-id",
                ),
                limit=10,
                window_seconds=60,
                client=redis,
            )
        )

    exc = exc_info.value

    assert exc.status_code == 429
    assert exc.detail == "Too many requests"
    assert exc.headers == {
        "Retry-After": "37",
    }


def test_rate_limit_redis_failure_is_fail_closed_503():
    redis = FakeRedis(
        error=RedisError(
            "simulated"
        )
    )

    with pytest.raises(
        HTTPException
    ) as exc_info:
        run(
            enforce_rate_limit(
                scope="oauth_start",
                identifiers=(
                    "user-id",
                ),
                limit=10,
                window_seconds=600,
                client=redis,
            )
        )

    assert (
        exc_info.value.status_code
        == 503
    )


def test_rate_limit_rejects_invalid_policy():
    redis = FakeRedis(
        result=[
            1,
            60,
        ]
    )

    with pytest.raises(ValueError):
        run(
            enforce_rate_limit(
                scope="",
                identifiers=(
                    "id",
                ),
                limit=1,
                window_seconds=60,
                client=redis,
            )
        )

    with pytest.raises(ValueError):
        run(
            enforce_rate_limit(
                scope="x",
                identifiers=(),
                limit=1,
                window_seconds=60,
                client=redis,
            )
        )


def test_handler_wiring_contract():
    expectations = {
        "backend/app/api/auth.py": (
            'scope="login"',
            "normalized_login_identifier_hash(",
            "payload.email",
            "limit=10",
            "window_seconds=600",
        ),

        "backend/app/api/content.py": (
            'scope="ai_generation"',
            "str(current_user.id)",
            "str(workspace_id)",
            "limit=10",
            "window_seconds=60",
        ),

        "backend/app/api/publications/publishing.py": (
            'scope="publish"',
            "str(current_user.id)",
            "str(workspace_id)",
            "limit=5",
            "window_seconds=60",
        ),

        "backend/app/api/oauth_connections.py": (
            'scope="oauth_start"',
            "str(current_user.id)",
            "limit=10",
            "window_seconds=600",
        ),
    }

    for relative, fragments in expectations.items():
        text = (
            ROOT
            / relative
        ).read_text(
            encoding="utf-8"
        )

        assert (
            text.count(
                "await enforce_rate_limit("
            )
            == 1
        )

        for fragment in fragments:
            assert fragment in text


def test_login_rate_limit_does_not_use_untrusted_ip_headers():
    text = (
        ROOT
        / "backend/app/api/auth.py"
    ).read_text(
        encoding="utf-8"
    ).lower()

    limiter_area = text[
        text.index(
            "await enforce_rate_limit("
        ):
        text.index(
            "await enforce_rate_limit("
        )
        + 700
    ]

    assert (
        "x-forwarded-for"
        not in limiter_area
    )

    assert (
        "x-real-ip"
        not in limiter_area
    )

    assert (
        "cf-connecting-ip"
        not in limiter_area
    )
