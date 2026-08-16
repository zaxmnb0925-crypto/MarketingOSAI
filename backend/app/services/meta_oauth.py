from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings


META_GRAPH_API_VERSION = "v23.0"
META_GRAPH_BASE_URL = (
    f"https://graph.facebook.com/"
    f"{META_GRAPH_API_VERSION}"
)


class MetaOAuthError(RuntimeError):
    pass


class MetaOAuthConfigurationError(
    MetaOAuthError
):
    pass


class MetaOAuthExchangeError(
    MetaOAuthError
):
    pass


class MetaOAuthIdentityError(
    MetaOAuthError
):
    pass


class MetaOAuthPageDiscoveryError(
    MetaOAuthError
):
    pass


@dataclass(frozen=True)
class MetaAccessToken:
    access_token: str = field(repr=False)
    token_type: str | None = None
    expires_in: int | None = None


@dataclass(frozen=True)
class MetaUserIdentity:
    id: str
    name: str | None = None


@dataclass(frozen=True)
class MetaManagedPage:
    id: str
    name: str
    access_token: str = field(repr=False)
    tasks: tuple[str, ...] = ()


def _require_meta_config() -> tuple[
    str,
    str,
    str,
]:
    app_id = settings.meta_app_id
    app_secret = settings.meta_app_secret
    redirect_uri = settings.meta_redirect_uri

    if not app_id:
        raise MetaOAuthConfigurationError(
            "META_APP_ID is not configured"
        )

    if not app_secret:
        raise MetaOAuthConfigurationError(
            "META_APP_SECRET is not configured"
        )

    if not redirect_uri:
        raise MetaOAuthConfigurationError(
            "META_REDIRECT_URI is not configured"
        )

    return (
        app_id,
        app_secret,
        redirect_uri,
    )


def _meta_error_message(
    payload: Any,
    fallback: str,
) -> str:
    if not isinstance(payload, dict):
        return fallback

    error = payload.get("error")

    if not isinstance(error, dict):
        return fallback

    error_type = error.get("type")
    error_code = error.get("code")
    error_subcode = error.get("error_subcode")

    safe_parts: list[str] = []

    if isinstance(error_type, str):
        safe_parts.append(
            f"type={error_type}"
        )

    if isinstance(error_code, int):
        safe_parts.append(
            f"code={error_code}"
        )

    if isinstance(error_subcode, int):
        safe_parts.append(
            f"subcode={error_subcode}"
        )

    if not safe_parts:
        return fallback

    return (
        f"{fallback}: "
        + ", ".join(safe_parts)
    )


async def exchange_code_for_access_token(
    code: str,
) -> MetaAccessToken:
    if not code:
        raise MetaOAuthExchangeError(
            "Meta authorization code is missing"
        )

    (
        app_id,
        app_secret,
        redirect_uri,
    ) = _require_meta_config()

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=False,
        ) as client:
            response = await client.post(
                (
                    f"{META_GRAPH_BASE_URL}"
                    "/oauth/access_token"
                ),
                data={
                    "client_id": app_id,
                    "redirect_uri":
                        redirect_uri,
                    "client_secret":
                        app_secret,
                    "code": code,
                },
            )
    except httpx.HTTPError as exc:
        raise MetaOAuthExchangeError(
            "Meta token endpoint request failed"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MetaOAuthExchangeError(
            "Meta token endpoint returned "
            "an invalid response"
        ) from exc

    if response.status_code >= 400:
        raise MetaOAuthExchangeError(
            _meta_error_message(
                payload,
                "Meta token exchange failed",
            )
        )

    if not isinstance(payload, dict):
        raise MetaOAuthExchangeError(
            "Meta token response is invalid"
        )

    access_token = payload.get(
        "access_token"
    )

    if not isinstance(
        access_token,
        str,
    ) or not access_token:
        raise MetaOAuthExchangeError(
            "Meta token response did not "
            "contain an access token"
        )

    token_type = payload.get(
        "token_type"
    )
    expires_in = payload.get(
        "expires_in"
    )

    return MetaAccessToken(
        access_token=access_token,
        token_type=(
            token_type
            if isinstance(
                token_type,
                str,
            )
            else None
        ),
        expires_in=(
            expires_in
            if isinstance(
                expires_in,
                int,
            )
            else None
        ),
    )


async def get_meta_user_identity(
    access_token: str,
) -> MetaUserIdentity:
    if not access_token:
        raise MetaOAuthIdentityError(
            "Meta access token is missing"
        )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=False,
        ) as client:
            response = await client.get(
                f"{META_GRAPH_BASE_URL}/me",
                params={
                    "fields": "id,name",
                },
                headers={
                    "Authorization":
                        f"Bearer {access_token}",
                },
            )
    except httpx.HTTPError as exc:
        raise MetaOAuthIdentityError(
            "Meta identity request failed"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise MetaOAuthIdentityError(
            "Meta identity endpoint returned "
            "an invalid response"
        ) from exc

    if response.status_code >= 400:
        raise MetaOAuthIdentityError(
            _meta_error_message(
                payload,
                "Meta identity request failed",
            )
        )

    if not isinstance(payload, dict):
        raise MetaOAuthIdentityError(
            "Meta identity response is invalid"
        )

    meta_user_id = payload.get("id")
    name = payload.get("name")

    if not isinstance(
        meta_user_id,
        str,
    ) or not meta_user_id:
        raise MetaOAuthIdentityError(
            "Meta identity response did not "
            "contain a user id"
        )

    return MetaUserIdentity(
        id=meta_user_id,
        name=(
            name
            if isinstance(name, str)
            else None
        ),
    )

async def get_meta_managed_pages(
    user_access_token: str,
) -> tuple[MetaManagedPage, ...]:
    if not user_access_token:
        raise MetaOAuthPageDiscoveryError(
            "Meta user access token is missing"
        )

    pages: list[MetaManagedPage] = []
    after: str | None = None

    # Fixed endpoint + cursor-only pagination.
    # We intentionally do not follow arbitrary paging.next URLs.
    for _ in range(20):
        params: dict[str, str | int] = {
            "fields": "id,name,access_token,tasks",
            "limit": 100,
        }

        if after:
            params["after"] = after

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"{META_GRAPH_BASE_URL}/me/accounts",
                    params=params,
                    headers={
                        "Authorization":
                            f"Bearer {user_access_token}",
                    },
                )
        except httpx.HTTPError as exc:
            raise MetaOAuthPageDiscoveryError(
                "Meta Page discovery request failed"
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise MetaOAuthPageDiscoveryError(
                "Meta Page discovery endpoint "
                "returned an invalid response"
            ) from exc

        if response.status_code >= 400:
            raise MetaOAuthPageDiscoveryError(
                _meta_error_message(
                    payload,
                    "Meta Page discovery failed",
                )
            )

        if not isinstance(payload, dict):
            raise MetaOAuthPageDiscoveryError(
                "Meta Page discovery response is invalid"
            )

        data = payload.get("data")

        if not isinstance(data, list):
            raise MetaOAuthPageDiscoveryError(
                "Meta Page discovery response "
                "did not contain a Page list"
            )

        for item in data:
            if not isinstance(item, dict):
                raise MetaOAuthPageDiscoveryError(
                    "Meta Page discovery returned "
                    "an invalid Page record"
                )

            page_id = item.get("id")
            page_name = item.get("name")
            page_access_token = item.get(
                "access_token"
            )
            raw_tasks = item.get("tasks", [])

            if (
                not isinstance(page_id, str)
                or not page_id
                or not isinstance(page_name, str)
                or not page_name
                or not isinstance(
                    page_access_token,
                    str,
                )
                or not page_access_token
            ):
                raise MetaOAuthPageDiscoveryError(
                    "Meta Page discovery returned "
                    "an incomplete Page record"
                )

            tasks: tuple[str, ...] = ()

            if isinstance(raw_tasks, list):
                tasks = tuple(
                    task
                    for task in raw_tasks
                    if isinstance(task, str)
                )

            pages.append(
                MetaManagedPage(
                    id=page_id,
                    name=page_name,
                    access_token=page_access_token,
                    tasks=tasks,
                )
            )

        paging = payload.get("paging")

        if not isinstance(paging, dict):
            break

        cursors = paging.get("cursors")

        if not isinstance(cursors, dict):
            break

        next_after = cursors.get("after")

        if (
            not isinstance(next_after, str)
            or not next_after
            or next_after == after
        ):
            break

        # A paging.next link indicates another page.
        # Without it, an "after" cursor alone is not
        # treated as proof that another request exists.
        if not paging.get("next"):
            break

        after = next_after
    else:
        raise MetaOAuthPageDiscoveryError(
            "Meta Page discovery pagination "
            "limit exceeded"
        )

    return tuple(pages)

