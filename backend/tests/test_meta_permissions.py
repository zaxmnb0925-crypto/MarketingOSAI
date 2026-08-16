import asyncio
from urllib.parse import parse_qs

import httpx

from app.services.meta_permissions import (
    META_REQUIRED_PAGE_PUBLISHING_PERMISSIONS,
    MetaGraphPermissionHTTPTransport,
    MetaPermissionProviderError,
)


APP_ID = "FAKE_APP_ID_123"
APP_SECRET = "FAKE_APP_SECRET_DO_NOT_LOG"
APP_TOKEN = "FAKE_APP_TOKEN_DO_NOT_LOG"

PAGE_ID = "119402794592265"
PAGE_TOKEN = "FAKE_PAGE_TOKEN_DO_NOT_LOG"


def assert_true(
    condition: bool,
    label: str,
) -> None:
    if not condition:
        raise AssertionError(label)


def make_transport(
    handler,
):
    return MetaGraphPermissionHTTPTransport(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        transport=httpx.MockTransport(
            handler
        ),
    )


async def success_case() -> None:
    calls = []

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        calls.append(
            request.url.path
        )

        if (
            request.url.path
            == "/v23.0/oauth/access_token"
        ):
            assert_true(
                request.method == "POST",
                "App token method mismatch",
            )

            assert_true(
                not request.url.params,
                "App secret appeared in URL",
            )

            body = parse_qs(
                request.content.decode(
                    "utf-8"
                )
            )

            assert_true(
                body.get(
                    "client_id"
                ) == [APP_ID],
                "App id missing",
            )

            assert_true(
                body.get(
                    "client_secret"
                ) == [APP_SECRET],
                "App secret body mismatch",
            )

            assert_true(
                PAGE_TOKEN
                not in request.content.decode(
                    "utf-8"
                ),
                "Page token leaked into "
                "App token request",
            )

            return httpx.Response(
                200,
                json={
                    "access_token":
                        APP_TOKEN,
                    "token_type":
                        "bearer",
                },
            )

        if (
            request.url.path
            == "/v23.0/debug_token"
        ):
            assert_true(
                request.method == "GET",
                "debug_token method mismatch",
            )

            assert_true(
                request.url.params.get(
                    "input_token"
                )
                == PAGE_TOKEN,
                "debug input token mismatch",
            )

            assert_true(
                request.headers.get(
                    "Authorization"
                )
                == f"Bearer {APP_TOKEN}",
                "App token header mismatch",
            )

            assert_true(
                "access_token"
                not in request.url.params,
                "App token appeared in URL",
            )

            return httpx.Response(
                200,
                json={
                    "data": {
                        "app_id":
                            APP_ID,
                        "type":
                            "PAGE",
                        "is_valid":
                            True,
                        "scopes": [
                            "public_profile",
                            "pages_show_list",
                            "pages_read_engagement",
                            "pages_manage_posts",
                        ],
                    }
                },
            )

        raise AssertionError(
            "Unexpected mock endpoint"
        )

    result = (
        await make_transport(
            handler
        ).inspect_page_token(
            page_id=PAGE_ID,
            page_access_token=PAGE_TOKEN,
        )
    )

    assert_true(
        result.publishing_ready,
        "ready token was blocked",
    )

    assert_true(
        result.is_valid,
        "valid flag missing",
    )

    assert_true(
        result.app_match,
        "App match missing",
    )

    assert_true(
        result.token_type == "PAGE",
        "PAGE type missing",
    )

    assert_true(
        not result.missing_required_permissions,
        "required permission missing",
    )

    assert_true(
        not result.target_mismatch_permissions,
        "unexpected target mismatch",
    )

    for permission in (
        META_REQUIRED_PAGE_PUBLISHING_PERMISSIONS
    ):
        assert_true(
            permission
            in result.granted_scopes,
            f"{permission} not persisted",
        )

    safe_repr = repr(result)

    for forbidden in (
        PAGE_TOKEN,
        APP_TOKEN,
        APP_SECRET,
    ):
        assert_true(
            forbidden not in safe_repr,
            "secret leaked through result repr",
        )

    assert_true(
        calls == [
            "/v23.0/oauth/access_token",
            "/v23.0/debug_token",
        ],
        "unexpected request sequence",
    )

    print(
        "valid PAGE permission inspection: PASS"
    )
    print(
        "all required publishing permissions: PASS"
    )
    print(
        "canonical scope result secret-free: PASS"
    )


async def missing_permission_case() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if (
            request.url.path
            == "/v23.0/oauth/access_token"
        ):
            return httpx.Response(
                200,
                json={
                    "access_token":
                        APP_TOKEN,
                },
            )

        return httpx.Response(
            200,
            json={
                "data": {
                    "app_id":
                        APP_ID,
                    "type":
                        "PAGE",
                    "is_valid":
                        True,
                    "scopes": [
                        "pages_show_list",
                        "pages_read_engagement",
                    ],
                }
            },
        )

    result = (
        await make_transport(
            handler
        ).inspect_page_token(
            page_id=PAGE_ID,
            page_access_token=PAGE_TOKEN,
        )
    )

    assert_true(
        not result.publishing_ready,
        "missing permission became ready",
    )

    assert_true(
        result.missing_required_permissions
        == (
            "pages_manage_posts",
        ),
        "missing permission result mismatch",
    )

    print(
        "missing pages_manage_posts blocks readiness: PASS"
    )


async def target_mismatch_case() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if (
            request.url.path
            == "/v23.0/oauth/access_token"
        ):
            return httpx.Response(
                200,
                json={
                    "access_token":
                        APP_TOKEN,
                },
            )

        return httpx.Response(
            200,
            json={
                "data": {
                    "app_id":
                        APP_ID,
                    "type":
                        "PAGE",
                    "is_valid":
                        True,
                    "scopes": [
                        "pages_show_list",
                        "pages_read_engagement",
                        "pages_manage_posts",
                    ],
                    "granular_scopes": [
                        {
                            "scope":
                                "pages_manage_posts",
                            "target_ids": [
                                "999999999999"
                            ],
                        }
                    ],
                }
            },
        )

    result = (
        await make_transport(
            handler
        ).inspect_page_token(
            page_id=PAGE_ID,
            page_access_token=PAGE_TOKEN,
        )
    )

    assert_true(
        not result.publishing_ready,
        "target mismatch became ready",
    )

    assert_true(
        result.target_mismatch_permissions
        == (
            "pages_manage_posts",
        ),
        "target mismatch result incorrect",
    )

    print(
        "explicit Page target mismatch blocks readiness: PASS"
    )


async def app_mismatch_case() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if (
            request.url.path
            == "/v23.0/oauth/access_token"
        ):
            return httpx.Response(
                200,
                json={
                    "access_token":
                        APP_TOKEN,
                },
            )

        return httpx.Response(
            200,
            json={
                "data": {
                    "app_id":
                        "OTHER_APP",
                    "type":
                        "PAGE",
                    "is_valid":
                        True,
                    "scopes": list(
                        META_REQUIRED_PAGE_PUBLISHING_PERMISSIONS
                    ),
                }
            },
        )

    result = (
        await make_transport(
            handler
        ).inspect_page_token(
            page_id=PAGE_ID,
            page_access_token=PAGE_TOKEN,
        )
    )

    assert_true(
        not result.app_match,
        "App mismatch not detected",
    )

    assert_true(
        not result.publishing_ready,
        "App mismatch became ready",
    )

    print(
        "configured App mismatch blocks readiness: PASS"
    )


async def safe_provider_error_case() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if (
            request.url.path
            == "/v23.0/oauth/access_token"
        ):
            return httpx.Response(
                200,
                json={
                    "access_token":
                        APP_TOKEN,
                },
            )

        return httpx.Response(
            400,
            json={
                "error": {
                    "message":
                        "SECRET_PROVIDER_MESSAGE",
                    "type":
                        "OAuthException",
                    "code":
                        190,
                    "error_subcode":
                        463,
                    "error_data": {
                        "token":
                            PAGE_TOKEN,
                    },
                    "fbtrace_id":
                        "SECRET_TRACE",
                }
            },
        )

    try:
        await make_transport(
            handler
        ).inspect_page_token(
            page_id=PAGE_ID,
            page_access_token=PAGE_TOKEN,
        )

    except MetaPermissionProviderError as exc:
        safe = str(exc)

        assert_true(
            "type=OAuthException"
            in safe,
            "safe type missing",
        )

        assert_true(
            "code=190"
            in safe,
            "safe code missing",
        )

        assert_true(
            "subcode=463"
            in safe,
            "safe subcode missing",
        )

        for forbidden in (
            "SECRET_PROVIDER_MESSAGE",
            "SECRET_TRACE",
            PAGE_TOKEN,
            APP_TOKEN,
            APP_SECRET,
        ):
            assert_true(
                forbidden not in safe,
                "provider secret leaked",
            )

    else:
        raise AssertionError(
            "provider error accepted"
        )

    print(
        "provider error secret isolation: PASS"
    )


async def timeout_case() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            (
                "SECRET_TIMEOUT "
                + PAGE_TOKEN
            ),
            request=request,
        )

    try:
        await make_transport(
            handler
        ).inspect_page_token(
            page_id=PAGE_ID,
            page_access_token=PAGE_TOKEN,
        )

    except MetaPermissionProviderError as exc:
        safe = str(exc)

        assert_true(
            safe
            == "Meta permission request failed",
            "timeout safe message mismatch",
        )

        assert_true(
            PAGE_TOKEN not in safe,
            "timeout leaked Page token",
        )

        assert_true(
            APP_SECRET not in safe,
            "timeout leaked App secret",
        )

    else:
        raise AssertionError(
            "timeout accepted"
        )

    print(
        "network exception isolation: PASS"
    )


async def main() -> None:
    await success_case()
    await missing_permission_case()
    await target_mismatch_case()
    await app_mismatch_case()
    await safe_provider_error_case()
    await timeout_case()

    print()
    print(
        "Meta permission MockTransport tests: PASS"
    )
    print(
        "Real Meta network calls: NONE"
    )
    print(
        "Real Page token used: NONE"
    )
    print(
        "Real App secret used: NONE"
    )


asyncio.run(main())
