import base64
import binascii
from uuid import UUID

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str
    redis_url: str
    secret_key: str
    openai_api_key: str
    oauth_token_encryption_key: str

    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    meta_redirect_uri: str | None = None
    meta_business_login_config_id: str | None = None

    #
    # Provider-side publishing is intentionally disabled
    # by default. Enabling the HTTP surface later must
    # require an explicit production configuration change.
    #
    real_publish_enabled: bool = False
    meta_publish_transport_enabled: bool = False

    meta_publish_canary_workspace_id: UUID | None = None
    meta_publish_canary_publication_id: UUID | None = None

    # v0.13F publishing operating mode.
    # True is deliberately fail-closed: only the exact
    # configured canary Workspace + Publication may pass.
    # Normal production publishing must explicitly set
    # this False after the normal-mode safety gates pass.
    meta_publish_canary_mode_enabled: bool = True

    # Application/release metadata.
    app_version: str = "0.13H"

    # API documentation is fail-closed by default.
    # Development environments may explicitly enable it
    # with API_DOCS_ENABLED=true.
    api_docs_enabled: bool = False

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32:
            raise ValueError("SECRET_KEY must be at least 32 bytes")
        return value

    @field_validator("oauth_token_encryption_key")
    @classmethod
    def validate_oauth_encryption_key(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(
                value.encode("ascii"),
                altchars=b"-_",
                validate=True,
            )
        except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
            raise ValueError(
                "OAUTH_TOKEN_ENCRYPTION_KEY must be a valid Fernet key"
            ) from exc
        if len(decoded) != 32:
            raise ValueError(
                "OAUTH_TOKEN_ENCRYPTION_KEY must decode to exactly 32 bytes"
            )
        return value

    @model_validator(mode="after")
    def reject_production_placeholders(self):
        if self.environment.strip().casefold() != "production":
            return self

        markers = (
            "replace",
            "changeme",
            "example",
            "test-only",
            "not-a-live",
        )
        secret = self.secret_key.casefold()
        secret_bytes = self.secret_key.encode("utf-8")
        if len(secret_bytes) < 64 or len(set(secret_bytes)) < 16 or any(
            marker in secret for marker in markers
        ):
            raise ValueError(
                "Production SECRET_KEY must be at least 64 bytes and not weak or a placeholder"
            )

        encryption_key = self.oauth_token_encryption_key.casefold()
        decoded = base64.urlsafe_b64decode(
            self.oauth_token_encryption_key.encode("ascii")
        )
        if any(marker in encryption_key for marker in markers) or len(set(decoded)) < 2:
            raise ValueError(
                "Production OAUTH_TOKEN_ENCRYPTION_KEY must not be a placeholder"
            )
        return self

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()
