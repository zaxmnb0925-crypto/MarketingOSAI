import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.services.meta_oauth import (
    META_GRAPH_BASE_URL,
)


class MetaPublishingError(RuntimeError):
    pass


class MetaPublishingValidationError(
    MetaPublishingError
):
    pass


class MetaPublishingProviderError(
    MetaPublishingError
):
    pass


class MetaPublishingOutcomeUnknown(
    MetaPublishingProviderError
):
    """
    The provider request may have reached Meta, but the
    caller cannot prove whether a post was created.

    This condition must never be automatically retried.
    """

    pass


@dataclass(frozen=True)
class MetaPageTextPostPlan:
    page_id: str

    # Exact approved Publication snapshot.
    # repr=False prevents accidental logging through
    # dataclass representations.
    message: str = field(repr=False)

    endpoint_path: str
    content_hash: str
    content_length: int


@dataclass(frozen=True)
class MetaPublishDryRun:
    provider: str
    platform: str
    action: str

    target_account_id: str
    endpoint_path: str

    content_hash: str
    content_length: int


@dataclass(frozen=True)
class MetaPublishResult:
    provider_post_id: str
    provider_permalink: str | None = None


class MetaPublishingTransport(Protocol):
    async def create_page_text_post(
        self,
        *,
        page_id: str,
        page_access_token: str,
        message: str,
    ) -> MetaPublishResult:
        ...


def _content_sha256(
    content: str,
) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def safe_meta_error_message(
    payload: Any,
    fallback: str,
) -> str:
    """
    Convert a Meta-style error response into a
    deliberately restricted operational message.

    Provider message text, request ids, trace ids,
    OAuth tokens and error_data are intentionally
    excluded.
    """
    if not isinstance(payload, dict):
        return fallback

    error = payload.get("error")

    if not isinstance(error, dict):
        return fallback

    safe_parts: list[str] = []

    error_type = error.get("type")
    error_code = error.get("code")
    error_subcode = error.get("error_subcode")

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


def build_meta_page_text_post_plan(
    page_id: str,
    message: str,
) -> MetaPageTextPostPlan:
    if not isinstance(page_id, str):
        raise MetaPublishingValidationError(
            "Meta Page id is invalid"
        )

    page_id = page_id.strip()

    if not page_id:
        raise MetaPublishingValidationError(
            "Meta Page id is required"
        )

    if not isinstance(message, str):
        raise MetaPublishingValidationError(
            "Publication content is invalid"
        )

    if not message.strip():
        raise MetaPublishingValidationError(
            "Publication content is empty"
        )

    return MetaPageTextPostPlan(
        page_id=page_id,
        message=message,
        endpoint_path=f"/{page_id}/feed",
        content_hash=_content_sha256(
            message
        ),
        content_length=len(message),
    )


def dry_run_meta_page_text_publish(
    page_id: str,
    message: str,
) -> MetaPublishDryRun:
    plan = build_meta_page_text_post_plan(
        page_id,
        message,
    )

    return MetaPublishDryRun(
        provider="meta",
        platform="facebook",
        action="create_page_text_post",
        target_account_id=plan.page_id,
        endpoint_path=plan.endpoint_path,
        content_hash=plan.content_hash,
        content_length=plan.content_length,
    )



class MetaGraphHTTPTransport:
    """
    Concrete Facebook Graph API transport.

    Security boundaries:
    - Page token is sent only in the Authorization header.
    - Page token is never placed in query parameters.
    - Redirects are disabled.
    - Raw provider error messages are never propagated.
    - Raw response bodies are never propagated.
    - Transport failures, HTTP 5xx responses, and
      ambiguous HTTP 2xx responses without a trustworthy
      provider post id are classified outcome-unknown so
      callers cannot safely auto-retry and duplicate posts.
    """

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Meta HTTP timeout must be positive"
            )

        self._transport = transport
        self._timeout = httpx.Timeout(
            timeout_seconds
        )

    async def create_page_text_post(
        self,
        *,
        page_id: str,
        page_access_token: str,
        message: str,
    ) -> MetaPublishResult:
        if (
            not isinstance(
                page_access_token,
                str,
            )
            or not page_access_token
        ):
            raise MetaPublishingValidationError(
                "Meta Page credential is missing"
            )

        plan = build_meta_page_text_post_plan(
            page_id,
            message,
        )

        url = (
            f"{META_GRAPH_BASE_URL}"
            f"{plan.endpoint_path}"
        )

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    url,
                    data={
                        "message": plan.message,
                    },
                    headers={
                        "Authorization":
                            f"Bearer {page_access_token}",
                        "Accept":
                            "application/json",
                    },
                )
        except httpx.RequestError:
            #
            # Once provider execution begins, a network
            # exception cannot safely prove that Meta did
            # not create the post.
            #
            raise MetaPublishingOutcomeUnknown(
                "Meta publishing outcome is unknown"
            ) from None

        try:
            payload = response.json()
        except ValueError:
            payload = None

        #
        # 5xx may occur after provider-side processing.
        # Never treat this as safely retryable.
        #
        if response.status_code >= 500:
            raise MetaPublishingOutcomeUnknown(
                "Meta publishing outcome is unknown"
            )

        if response.status_code >= 300:
            raise MetaPublishingProviderError(
                safe_meta_error_message(
                    payload,
                    "Meta publishing request was rejected",
                )
            )

        if not isinstance(payload, dict):
            #
            # Meta returned 2xx, so provider-side creation
            # may already have happened. Without a valid
            # response body we cannot safely prove failure.
            #
            raise MetaPublishingOutcomeUnknown(
                "Meta publishing outcome is unknown"
            )

        provider_post_id = payload.get("id")

        if (
            not isinstance(
                provider_post_id,
                str,
            )
            or not provider_post_id.strip()
        ):
            #
            # A 2xx response without a trustworthy post id
            # is ambiguous. The post may already exist.
            # Never classify this as a definite failure.
            #
            raise MetaPublishingOutcomeUnknown(
                "Meta publishing outcome is unknown"
            )

        return MetaPublishResult(
            provider_post_id=provider_post_id,
            provider_permalink=None,
        )


async def publish_meta_page_text_with_transport(
    *,
    page_id: str,
    page_access_token: str,
    message: str,
    transport: MetaPublishingTransport,
) -> MetaPublishResult:
    """
    Provider-neutral execution boundary.

    This function performs no network activity itself.
    A concrete transport must be injected by the caller.

    v0.13C ships without a real Meta HTTP transport.
    """

    if (
        not isinstance(
            page_access_token,
            str,
        )
        or not page_access_token
    ):
        raise MetaPublishingValidationError(
            "Meta Page credential is missing"
        )

    plan = build_meta_page_text_post_plan(
        page_id,
        message,
    )

    try:
        result = (
            await transport.create_page_text_post(
                page_id=plan.page_id,
                page_access_token=page_access_token,
                message=plan.message,
            )
        )
    except MetaPublishingError:
        raise
    except Exception:
        # Never propagate arbitrary transport exception
        # text because it may contain provider payloads,
        # request headers, tokens or user content.
        raise MetaPublishingProviderError(
            "Meta publishing transport failed"
        ) from None

    if not isinstance(
        result,
        MetaPublishResult,
    ):
        raise MetaPublishingProviderError(
            "Meta publishing transport "
            "returned an invalid result"
        )

    if (
        not isinstance(
            result.provider_post_id,
            str,
        )
        or not result.provider_post_id.strip()
    ):
        raise MetaPublishingProviderError(
            "Meta publishing response "
            "did not contain a post id"
        )

    return result
