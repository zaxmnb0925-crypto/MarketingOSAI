import asyncio
from dataclasses import dataclass

from app.services.meta_permissions import (
    MetaPagePermissionVerification,
    MetaPermissionNotReadyError,
    verify_meta_managed_pages_for_publishing,
)


PAGE_TOKEN = "FAKE_PAGE_TOKEN_BRIDGE"


@dataclass(frozen=True)
class FakePage:
    id: str
    access_token: str


class ReadyTransport:
    def __init__(self):
        self.calls = 0

    async def inspect_page_token(
        self,
        *,
        page_id: str,
        page_access_token: str,
    ):
        self.calls += 1

        assert (
            page_access_token
            == PAGE_TOKEN
        )

        return MetaPagePermissionVerification(
            page_id=page_id,
            is_valid=True,
            app_match=True,
            token_type="PAGE",
            granted_scopes=(
                "pages_manage_posts",
                "pages_read_engagement",
                "pages_show_list",
                "public_profile",
            ),
            missing_required_permissions=(),
            target_mismatch_permissions=(),
            publishing_ready=True,
        )


class NotReadyTransport:
    async def inspect_page_token(
        self,
        *,
        page_id: str,
        page_access_token: str,
    ):
        return MetaPagePermissionVerification(
            page_id=page_id,
            is_valid=True,
            app_match=True,
            token_type="PAGE",
            granted_scopes=(
                "pages_show_list",
            ),
            missing_required_permissions=(
                "pages_manage_posts",
                "pages_read_engagement",
            ),
            target_mismatch_permissions=(),
            publishing_ready=False,
        )


async def ready_case():
    transport = ReadyTransport()

    result = (
        await verify_meta_managed_pages_for_publishing(
            (
                FakePage(
                    id="119402794592265",
                    access_token=PAGE_TOKEN,
                ),
            ),
            transport,
        )
    )

    assert transport.calls == 1

    assert (
        result["119402794592265"]
        == (
            "pages_manage_posts,"
            "pages_read_engagement,"
            "pages_show_list,"
            "public_profile"
        )
    )

    assert (
        PAGE_TOKEN
        not in repr(result)
    )

    print(
        "verified Page -> canonical scopes: PASS"
    )

    print(
        "bridge output token isolation: PASS"
    )


async def not_ready_case():
    try:
        await verify_meta_managed_pages_for_publishing(
            (
                FakePage(
                    id="119402794592265",
                    access_token=PAGE_TOKEN,
                ),
            ),
            NotReadyTransport(),
        )

    except MetaPermissionNotReadyError as exc:
        safe = str(exc)

        assert (
            safe
            == (
                "Meta Page publishing "
                "permissions are incomplete"
            )
        )

        assert PAGE_TOKEN not in safe

    else:
        raise AssertionError(
            "not-ready Page was accepted"
        )

    print(
        "incomplete permission blocks persistence: PASS"
    )


async def duplicate_page_case():
    transport = ReadyTransport()

    try:
        await verify_meta_managed_pages_for_publishing(
            (
                FakePage(
                    id="119402794592265",
                    access_token=PAGE_TOKEN,
                ),
                FakePage(
                    id="119402794592265",
                    access_token=PAGE_TOKEN,
                ),
            ),
            transport,
        )

    except Exception as exc:
        assert (
            str(exc)
            == "Duplicate Meta Page id"
        )

    else:
        raise AssertionError(
            "duplicate Page id accepted"
        )

    print(
        "duplicate Page id blocked: PASS"
    )


async def main():
    await ready_case()
    await not_ready_case()
    await duplicate_page_case()

    print()
    print(
        "Permission callback bridge tests: PASS"
    )

    print(
        "Real Meta network calls: NONE"
    )

    print(
        "Real tokens used: NONE"
    )


asyncio.run(main())
