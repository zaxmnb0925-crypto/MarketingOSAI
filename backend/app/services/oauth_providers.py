from dataclasses import dataclass
from urllib.parse import urlencode

from app.core.config import settings


class UnsupportedOAuthProvider(
    RuntimeError
):
    pass


class OAuthProviderNotConfigured(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class OAuthProviderConfig:
    name: str
    authorization_url: str
    scopes: tuple[str, ...]


PROVIDERS = {
    "meta": OAuthProviderConfig(
        name="meta",
        authorization_url=(
            "https://www.facebook.com/"
            "v23.0/dialog/oauth"
        ),
        scopes=(
            "public_profile",
            "pages_show_list",
        ),
    ),
}


def get_oauth_provider(
    provider: str,
) -> OAuthProviderConfig:
    config = PROVIDERS.get(provider)

    if config is None:
        raise UnsupportedOAuthProvider(
            f"Unsupported OAuth provider: {provider}"
        )

    return config


def build_authorization_url(
    provider: str,
    state: str,
) -> str:
    config = get_oauth_provider(
        provider
    )

    if provider == "meta":
        if not settings.meta_app_id:
            raise OAuthProviderNotConfigured(
                "META_APP_ID is not configured"
            )

        if not settings.meta_redirect_uri:
            raise OAuthProviderNotConfigured(
                "META_REDIRECT_URI is not configured"
            )

        if not settings.meta_business_login_config_id:
            raise OAuthProviderNotConfigured(
                "META_BUSINESS_LOGIN_CONFIG_ID "
                "is not configured"
            )

        # Facebook Login for Business:
        # permissions/assets are defined by config_id.
        # System User Access Token configurations use
        # Authorization Code grant and must not send
        # the legacy scope parameter.
        query = urlencode(
            {
                "client_id":
                    settings.meta_app_id,
                "redirect_uri":
                    settings.meta_redirect_uri,
                "response_type":
                    "code",
                "override_default_response_type":
                    "true",
                "config_id":
                    settings.meta_business_login_config_id,
                "state":
                    state,
            }
        )

        return (
            f"{config.authorization_url}"
            f"?{query}"
        )

    raise UnsupportedOAuthProvider(
        f"Unsupported OAuth provider: {provider}"
    )
