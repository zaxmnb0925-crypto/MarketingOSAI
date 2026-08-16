from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.services.meta_oauth import (
    META_GRAPH_BASE_URL,
)


META_REQUIRED_PAGE_PUBLISHING_PERMISSIONS = (
    "pages_manage_posts",
    "pages_read_engagement",
    "pages_show_list",
)


class MetaPermissionError(RuntimeError):
    pass


class MetaPermissionValidationError(
    MetaPermissionError
):
    pass


class MetaPermissionProviderError(
    MetaPermissionError
):
    pass


class MetaPermissionNotReadyError(
    MetaPermissionError
):
    pass


@dataclass(frozen=True)
class MetaPagePermissionVerification:
    page_id: str
    is_valid: bool
    app_match: bool
    token_type: str | None

    granted_scopes: tuple[str, ...]
    missing_required_permissions: tuple[str, ...]
    target_mismatch_permissions: tuple[str, ...]

    publishing_ready: bool

    @property
    def canonical_scopes(self) -> str:
        return ",".join(
            self.granted_scopes
        )


class MetaPermissionTransport(Protocol):
    async def inspect_page_token(
        self,
        *,
        page_id: str,
        page_access_token: str,
    ) -> MetaPagePermissionVerification:
        ...


def _safe_meta_error_message(
    payload: Any,
    fallback: str,
) -> str:
    """
    Return only restricted Meta operational metadata.

    Provider messages, error_data, trace ids, tokens,
    app secrets and raw response bodies are excluded.
    """
    if not isinstance(payload, dict):
        return fallback

    error = payload.get("error")

    if not isinstance(error, dict):
        return fallback

    parts: list[str] = []

    error_type = error.get("type")
    error_code = error.get("code")
    error_subcode = error.get(
        "error_subcode"
    )

    if isinstance(error_type, str):
        parts.append(
            f"type={error_type}"
        )

    if isinstance(error_code, int):
        parts.append(
            f"code={error_code}"
        )

    if isinstance(error_subcode, int):
        parts.append(
            f"subcode={error_subcode}"
        )

    if not parts:
        return fallback

    return (
        f"{fallback}: "
        + ", ".join(parts)
    )


def _normalize_scopes(
    data: dict[str, Any],
) -> tuple[
    tuple[str, ...],
    dict[str, set[str]],
]:
    scopes: set[str] = set()

    raw_scopes = data.get("scopes")

    if isinstance(raw_scopes, list):
        scopes.update(
            value
            for value in raw_scopes
            if isinstance(value, str)
            and value
        )

    targets: dict[str, set[str]] = {}

    granular = data.get(
        "granular_scopes"
    )

    if isinstance(granular, list):
        for item in granular:
            if not isinstance(item, dict):
                continue

            scope = item.get("scope")

            if (
                not isinstance(scope, str)
                or not scope
            ):
                continue

            scopes.add(scope)

            raw_targets = item.get(
                "target_ids"
            )

            if not isinstance(
                raw_targets,
                list,
            ):
                continue

            normalized_targets = {
                str(value)
                for value in raw_targets
                if isinstance(
                    value,
                    (str, int),
                )
            }

            if normalized_targets:
                targets.setdefault(
                    scope,
                    set(),
                ).update(
                    normalized_targets
                )

    return (
        tuple(sorted(scopes)),
        targets,
    )


class MetaGraphPermissionHTTPTransport:
    """
    Concrete read-only Meta permission introspection.

    This transport:
    - obtains an App access token using client credentials;
    - calls /debug_token for the Page token;
    - never returns or persists either token;
    - never exposes raw provider messages;
    - follows no redirects.

    The Page token is supplied to Meta's debug endpoint
    only for introspection and is never logged here.
    """

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        transport: (
            httpx.AsyncBaseTransport
            | None
        ) = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if (
            not isinstance(app_id, str)
            or not app_id
        ):
            raise MetaPermissionValidationError(
                "Meta App id is missing"
            )

        if (
            not isinstance(
                app_secret,
                str,
            )
            or not app_secret
        ):
            raise MetaPermissionValidationError(
                "Meta App secret is missing"
            )

        if timeout_seconds <= 0:
            raise MetaPermissionValidationError(
                "Meta permission timeout "
                "must be positive"
            )

        self._app_id = app_id
        self._app_secret = app_secret
        self._transport = transport
        self._timeout = httpx.Timeout(
            timeout_seconds
        )

    async def inspect_page_token(
        self,
        *,
        page_id: str,
        page_access_token: str,
    ) -> MetaPagePermissionVerification:
        if (
            not isinstance(page_id, str)
            or not page_id.strip()
        ):
            raise MetaPermissionValidationError(
                "Meta Page id is missing"
            )

        page_id = page_id.strip()

        if (
            not isinstance(
                page_access_token,
                str,
            )
            or not page_access_token
        ):
            raise MetaPermissionValidationError(
                "Meta Page credential is missing"
            )

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                app_response = await client.post(
                    (
                        f"{META_GRAPH_BASE_URL}"
                        "/oauth/access_token"
                    ),
                    data={
                        "client_id":
                            self._app_id,
                        "client_secret":
                            self._app_secret,
                        "grant_type":
                            "client_credentials",
                    },
                    headers={
                        "Accept":
                            "application/json",
                    },
                )

                try:
                    app_payload = (
                        app_response.json()
                    )
                except ValueError:
                    raise MetaPermissionProviderError(
                        "Meta App token response "
                        "is invalid"
                    ) from None

                if (
                    app_response.status_code
                    >= 400
                ):
                    raise MetaPermissionProviderError(
                        _safe_meta_error_message(
                            app_payload,
                            "Meta App token "
                            "request failed",
                        )
                    )

                if not isinstance(
                    app_payload,
                    dict,
                ):
                    raise MetaPermissionProviderError(
                        "Meta App token response "
                        "is invalid"
                    )

                app_token = app_payload.get(
                    "access_token"
                )

                if (
                    not isinstance(
                        app_token,
                        str,
                    )
                    or not app_token
                ):
                    raise MetaPermissionProviderError(
                        "Meta App token response "
                        "did not contain a token"
                    )

                debug_response = (
                    await client.get(
                        (
                            f"{META_GRAPH_BASE_URL}"
                            "/debug_token"
                        ),
                        params={
                            "input_token":
                                page_access_token,
                        },
                        headers={
                            "Authorization":
                                f"Bearer {app_token}",
                            "Accept":
                                "application/json",
                        },
                    )
                )

        except MetaPermissionError:
            raise

        except httpx.RequestError:
            raise MetaPermissionProviderError(
                "Meta permission request failed"
            ) from None

        finally:
            if "app_token" in locals():
                app_token = None

        try:
            debug_payload = (
                debug_response.json()
            )
        except ValueError:
            raise MetaPermissionProviderError(
                "Meta permission response "
                "is invalid"
            ) from None

        if (
            debug_response.status_code
            >= 400
        ):
            raise MetaPermissionProviderError(
                _safe_meta_error_message(
                    debug_payload,
                    "Meta permission "
                    "inspection failed",
                )
            )

        if not isinstance(
            debug_payload,
            dict,
        ):
            raise MetaPermissionProviderError(
                "Meta permission response "
                "is invalid"
            )

        data = debug_payload.get("data")

        if not isinstance(data, dict):
            raise MetaPermissionProviderError(
                "Meta permission response "
                "did not contain token data"
            )

        granted_scopes, targets = (
            _normalize_scopes(data)
        )

        granted_set = set(
            granted_scopes
        )

        missing = tuple(
            permission
            for permission
            in (
                META_REQUIRED_PAGE_PUBLISHING_PERMISSIONS
            )
            if permission
            not in granted_set
        )

        target_mismatches: list[str] = []

        for permission in (
            META_REQUIRED_PAGE_PUBLISHING_PERMISSIONS
        ):
            explicit_targets = (
                targets.get(permission)
            )

            if (
                explicit_targets
                and page_id
                not in explicit_targets
            ):
                target_mismatches.append(
                    permission
                )

        is_valid = (
            data.get("is_valid")
            is True
        )

        debug_app_id = data.get(
            "app_id"
        )

        app_match = (
            str(debug_app_id)
            == str(self._app_id)
        )

        token_type = data.get(
            "type"
        )

        if not isinstance(
            token_type,
            str,
        ):
            token_type = None

        page_type = (
            token_type is not None
            and token_type.upper()
            == "PAGE"
        )

        publishing_ready = (
            is_valid
            and app_match
            and page_type
            and not missing
            and not target_mismatches
        )

        return MetaPagePermissionVerification(
            page_id=page_id,
            is_valid=is_valid,
            app_match=app_match,
            token_type=token_type,
            granted_scopes=granted_scopes,
            missing_required_permissions=(
                missing
            ),
            target_mismatch_permissions=(
                tuple(
                    sorted(
                        target_mismatches
                    )
                )
            ),
            publishing_ready=(
                publishing_ready
            ),
        )


async def verify_meta_managed_pages_for_publishing(
    pages,
    transport: MetaPermissionTransport,
) -> dict[str, str]:
    """
    Verify every discovered Meta Page before persistence.

    Returns:
        page_id -> canonical verified scope string

    No token is returned, logged, or persisted here.
    """
    verified_scopes: dict[str, str] = {}

    for page in pages:
        page_id = getattr(
            page,
            "id",
            None,
        )

        page_access_token = getattr(
            page,
            "access_token",
            None,
        )

        if (
            not isinstance(page_id, str)
            or not page_id
        ):
            raise MetaPermissionValidationError(
                "Meta Page id is missing"
            )

        if page_id in verified_scopes:
            raise MetaPermissionValidationError(
                "Duplicate Meta Page id"
            )

        if (
            not isinstance(
                page_access_token,
                str,
            )
            or not page_access_token
        ):
            raise MetaPermissionValidationError(
                "Meta Page credential is missing"
            )

        verification = (
            await transport.inspect_page_token(
                page_id=page_id,
                page_access_token=(
                    page_access_token
                ),
            )
        )

        if not verification.publishing_ready:
            raise MetaPermissionNotReadyError(
                "Meta Page publishing "
                "permissions are incomplete"
            )

        canonical_scopes = (
            verification.canonical_scopes
        )

        if not canonical_scopes:
            raise MetaPermissionValidationError(
                "Verified Meta scopes are empty"
            )

        verified_scopes[
            page_id
        ] = canonical_scopes

    if not verified_scopes:
        raise MetaPermissionValidationError(
            "No Meta Pages were verified"
        )

    return verified_scopes

