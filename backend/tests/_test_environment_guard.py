"""Fail-closed validation for clean-room backend test environments."""

from __future__ import annotations

import os
import re
from urllib.parse import unquote, urlsplit


class TestIsolationError(RuntimeError):
    """Raised before tests import application resource clients."""


_LOOPBACK_HOSTS = {
    "127.0.0.1",
    "::1",
    "localhost",
}

_TEST_DATABASE_NAME = re.compile(
    r"^marketingos_test_[a-z0-9][a-z0-9_]*$"
)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()

    if not value:
        raise TestIsolationError(
            f"required test environment variable is missing: {name}"
        )

    return value


def _require_false(name: str) -> None:
    if _required(name).lower() != "false":
        raise TestIsolationError(
            f"test safety flag must be false: {name}"
        )


def _url(name: str):
    raw = _required(name)

    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise TestIsolationError(
            f"invalid test URL structure: {name}"
        ) from exc

    if host not in _LOOPBACK_HOSTS:
        raise TestIsolationError(
            f"test endpoint must use a loopback host: {name}"
        )

    if port is None:
        raise TestIsolationError(
            f"test endpoint must specify an explicit port: {name}"
        )

    return parsed, port


def _validate_database_url(mode: str) -> None:
    parsed, port = _url("DATABASE_URL")

    if parsed.scheme not in {
        "postgresql",
        "postgresql+asyncpg",
    }:
        raise TestIsolationError(
            "DATABASE_URL must use PostgreSQL"
        )

    database_name = unquote(parsed.path.lstrip("/"))

    if not _TEST_DATABASE_NAME.fullmatch(database_name):
        raise TestIsolationError(
            "DATABASE_URL must name an approved marketingos_test_* database"
        )

    if mode == "integration":
        if port == 5432:
            raise TestIsolationError(
                "integration PostgreSQL must use a non-default disposable port"
            )

        if not parsed.username or parsed.password is None:
            raise TestIsolationError(
                "integration PostgreSQL requires synthetic test credentials"
            )


def _validate_redis_url(mode: str) -> None:
    parsed, port = _url("REDIS_URL")

    if parsed.scheme not in {"redis", "rediss"}:
        raise TestIsolationError(
            "REDIS_URL must use a Redis URL scheme"
        )

    try:
        database_index = int(parsed.path.lstrip("/") or "0")
    except ValueError as exc:
        raise TestIsolationError(
            "REDIS_URL must use a numeric test database index"
        ) from exc

    if not 0 <= database_index <= 15:
        raise TestIsolationError(
            "REDIS_URL database index must be between 0 and 15"
        )

    if mode == "integration":
        if port == 6379:
            raise TestIsolationError(
                "integration Redis must use a non-default disposable port"
            )

        if database_index == 0:
            raise TestIsolationError(
                "integration Redis must not use default database zero"
            )


def validate_test_environment() -> str:
    if _required("ENVIRONMENT") != "test":
        raise TestIsolationError(
            "ENVIRONMENT must be exactly test"
        )

    mode = _required("MARKETINGOS_TEST_MODE")

    if mode not in {"no-external", "integration"}:
        raise TestIsolationError(
            "MARKETINGOS_TEST_MODE must be no-external or integration"
        )

    _require_false("REAL_PUBLISH_ENABLED")
    _require_false("META_PUBLISH_TRANSPORT_ENABLED")
    _require_false("API_DOCS_ENABLED")

    _required("SECRET_KEY")
    _required("OPENAI_API_KEY")
    _required("OAUTH_TOKEN_ENCRYPTION_KEY")

    _validate_database_url(mode)
    _validate_redis_url(mode)

    if mode == "integration":
        if _required("MARKETINGOS_TEST_RESOURCE_SCOPE") != "disposable":
            raise TestIsolationError(
                "integration resources must be explicitly marked disposable"
            )

    return mode
