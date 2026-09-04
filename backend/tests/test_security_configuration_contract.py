import base64

import pytest
from pydantic import ValidationError

from app.core.config import Settings


VALID_FERNET_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode()


def settings_input(**overrides):
    values = {
        "environment": "test",
        "database_url": "postgresql+asyncpg://test@127.0.0.1:1/test",
        "redis_url": "redis://127.0.0.1:1/15",
        "secret_key": "test-only-synthetic-secret-at-least-32-bytes",
        "openai_api_key": "test-only-not-a-live-key",
        "oauth_token_encryption_key": VALID_FERNET_KEY,
    }
    values.update(overrides)
    return values


def test_rejects_short_jwt_secret_without_echoing_value():
    secret = "too-short-private-value"
    with pytest.raises(ValidationError) as raised:
        Settings(**settings_input(secret_key=secret))
    assert secret not in str(raised.value)


@pytest.mark.parametrize("key", ["invalid", base64.urlsafe_b64encode(b"short").decode()])
def test_rejects_invalid_fernet_key_without_echoing_value(key):
    with pytest.raises(ValidationError) as raised:
        Settings(**settings_input(oauth_token_encryption_key=key))
    assert key not in str(raised.value)


def test_accepts_valid_test_security_configuration():
    settings = Settings(**settings_input())
    assert len(settings.secret_key.encode("utf-8")) >= 32


@pytest.mark.parametrize(
    "secret",
    [
        "replace-with-a-long-random-secret" + "x" * 32,
        "test-only-" + "x" * 64,
        "x" * 63,
        "x" * 64,
    ],
)
def test_production_rejects_weak_or_placeholder_jwt_secret(secret):
    with pytest.raises(ValidationError):
        Settings(**settings_input(environment="production", secret_key=secret))


def test_production_rejects_placeholder_fernet_key():
    repeated_key = base64.urlsafe_b64encode(b"A" * 32).decode()
    with pytest.raises(ValidationError):
        Settings(
            **settings_input(
                environment="production",
                secret_key="s" * 64,
                oauth_token_encryption_key=repeated_key,
            )
        )


def test_production_accepts_strong_security_configuration():
    settings = Settings(
        **settings_input(
            environment="production",
            secret_key="strong-production-key-material-" + "s" * 40,
        )
    )
    assert settings.environment == "production"
