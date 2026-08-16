import asyncio
from urllib.parse import parse_qs

import httpx

from app.services.meta_publishing import (
    MetaGraphHTTPTransport,
    MetaPublishResult,
    MetaPublishingOutcomeUnknown,
    MetaPublishingProviderError,
    MetaPublishingTransport,
    publish_meta_page_text_with_transport,
)


PAGE_ID = "119402794592265"

FAKE_TOKEN = (
    "FAKE_PAGE_TOKEN_DO_NOT_LOG"
)

MESSAGE = (
    "v0.13D mock-only publication content"
)


def assert_true(
    condition: bool,
    label: str,
) -> None:
    if not condition:
        raise AssertionError(label)


async def test_success() -> None:
    seen = {
        "called": False,
    }

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        seen["called"] = True

        assert_true(
            request.method == "POST",
            "success method mismatch",
        )

        assert_true(
            request.url.path
            == f"/v23.0/{PAGE_ID}/feed",
            "success URL path mismatch",
        )

        assert_true(
            "access_token"
            not in request.url.params,
            "token appeared in query string",
        )

        auth = request.headers.get(
            "Authorization"
        )

        assert_true(
            auth == f"Bearer {FAKE_TOKEN}",
            "Authorization header mismatch",
        )

        body = parse_qs(
            request.content.decode(
                "utf-8"
            )
        )

        assert_true(
            body.get("message") == [MESSAGE],
            "message body mismatch",
        )

        return httpx.Response(
            200,
            json={
                "id": "119402794592265_123456789",
            },
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    result = (
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )
    )

    assert_true(
        seen["called"],
        "mock transport was not called",
    )

    assert_true(
        isinstance(
            result,
            MetaPublishResult,
        ),
        "result type mismatch",
    )

    assert_true(
        result.provider_post_id
        == "119402794592265_123456789",
        "post id mismatch",
    )


async def test_safe_400_error() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "message":
                        "SECRET_PROVIDER_MESSAGE",
                    "type":
                        "OAuthException",
                    "code":
                        200,
                    "error_subcode":
                        2999007,
                    "error_data": {
                        "token":
                            FAKE_TOKEN,
                    },
                    "fbtrace_id":
                        "SECRET_TRACE_ID",
                }
            },
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )
    except MetaPublishingProviderError as exc:
        safe = str(exc)

        assert_true(
            "type=OAuthException" in safe,
            "safe error type missing",
        )

        assert_true(
            "code=200" in safe,
            "safe error code missing",
        )

        assert_true(
            "subcode=2999007" in safe,
            "safe error subcode missing",
        )

        for forbidden in (
            "SECRET_PROVIDER_MESSAGE",
            "SECRET_TRACE_ID",
            FAKE_TOKEN,
        ):
            assert_true(
                forbidden not in safe,
                "provider secret leaked",
            )
    else:
        raise AssertionError(
            "400 response was not rejected"
        )


async def test_5xx_is_unknown() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "error": {
                    "message":
                        "SECRET_5XX_BODY",
                    "type":
                        "ServerError",
                    "code":
                        2,
                }
            },
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )
    except MetaPublishingOutcomeUnknown as exc:
        safe = str(exc)

        assert_true(
            safe
            == "Meta publishing outcome is unknown",
            "5xx unknown message mismatch",
        )

        assert_true(
            "SECRET_5XX_BODY" not in safe,
            "5xx body leaked",
        )
    else:
        raise AssertionError(
            "5xx was not classified unknown"
        )


async def test_timeout_is_unknown() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "SECRET_TIMEOUT_DETAIL",
            request=request,
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )
    except MetaPublishingOutcomeUnknown as exc:
        safe = str(exc)

        assert_true(
            safe
            == "Meta publishing outcome is unknown",
            "timeout unknown message mismatch",
        )

        assert_true(
            "SECRET_TIMEOUT_DETAIL"
            not in safe,
            "timeout detail leaked",
        )

        assert_true(
            FAKE_TOKEN not in safe,
            "token leaked in timeout",
        )
    else:
        raise AssertionError(
            "timeout was not classified unknown"
        )


async def test_invalid_success_body() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )

    except MetaPublishingOutcomeUnknown as exc:
        safe = str(exc)

        assert_true(
            safe
            == "Meta publishing outcome is unknown",
            "invalid-2xx unknown message mismatch",
        )

        assert_true(
            FAKE_TOKEN not in safe,
            "token leaked in invalid 2xx",
        )

    else:
        raise AssertionError(
            "invalid 2xx was not outcome-unknown"
        )


async def test_missing_post_id() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
            },
        )

    transport = MetaGraphHTTPTransport(
        transport=httpx.MockTransport(
            handler
        )
    )

    try:
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )

    except MetaPublishingOutcomeUnknown as exc:
        safe = str(exc)

        assert_true(
            safe
            == "Meta publishing outcome is unknown",
            "missing-id unknown message mismatch",
        )

        assert_true(
            FAKE_TOKEN not in safe,
            "token leaked in missing-id 2xx",
        )

    else:
        raise AssertionError(
            "missing-id 2xx was not outcome-unknown"
        )


class ExplodingTransport:
    async def create_page_text_post(
        self,
        *,
        page_id: str,
        page_access_token: str,
        message: str,
    ) -> MetaPublishResult:
        raise RuntimeError(
            "SECRET_ARBITRARY_EXCEPTION "
            + page_access_token
        )


async def test_wrapper_sanitizes_unknown_exception(
) -> None:
    transport: MetaPublishingTransport = (
        ExplodingTransport()
    )

    try:
        await publish_meta_page_text_with_transport(
            page_id=PAGE_ID,
            page_access_token=FAKE_TOKEN,
            message=MESSAGE,
            transport=transport,
        )
    except MetaPublishingProviderError as exc:
        safe = str(exc)

        assert_true(
            safe
            == "Meta publishing transport failed",
            "wrapper safe error mismatch",
        )

        assert_true(
            FAKE_TOKEN not in safe,
            "wrapper leaked token",
        )

        assert_true(
            "SECRET_ARBITRARY_EXCEPTION"
            not in safe,
            "wrapper leaked exception",
        )
    else:
        raise AssertionError(
            "arbitrary transport error escaped"
        )


async def main() -> None:
    tests = (
        (
            "success mock",
            test_success,
        ),
        (
            "safe 400 error",
            test_safe_400_error,
        ),
        (
            "5xx outcome unknown",
            test_5xx_is_unknown,
        ),
        (
            "timeout outcome unknown",
            test_timeout_is_unknown,
        ),
        (
            "invalid success body",
            test_invalid_success_body,
        ),
        (
            "missing post id",
            test_missing_post_id,
        ),
        (
            "wrapper exception isolation",
            test_wrapper_sanitizes_unknown_exception,
        ),
    )

    for label, test in tests:
        await test()
        print(
            f"{label}: PASS"
        )

    print()
    print(
        "Mock HTTP transport tests: PASS"
    )
    print(
        "Real Meta network calls: NONE"
    )


asyncio.run(main())
