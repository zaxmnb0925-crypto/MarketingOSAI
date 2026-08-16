from uuid import UUID

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

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
