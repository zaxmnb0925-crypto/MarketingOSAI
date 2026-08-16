import asyncio
from types import SimpleNamespace
from uuid import UUID

from fastapi import Response

import sys as _publication_compat_sys
from pathlib import Path as _publication_compat_Path

_publication_compat_dir = str(
    _publication_compat_Path(
        __file__
    ).resolve().parent
)

if (
    _publication_compat_dir
    not in _publication_compat_sys.path
):
    _publication_compat_sys.path.insert(
        0,
        _publication_compat_dir,
    )

from _publication_test_compat import (
    publication_publishing_source_path,
    publication_source_paths,
    publication_source_text,
    publications,
)


WORKSPACE_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

PUBLICATION_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)

USER_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)

CONTENT_HASH = "a" * 64

CONFIRMATION = (
    "FAKE_CONFIRMATION_VALUE_"
    "NOT_A_REAL_BEARER_1234567890"
)


class FakeDB:
    pass


async def main():
    calls = []

    async def authorize(
        db,
        user,
        workspace_id,
    ):
        calls.append(
            "authorize"
        )

    async def dry_run(
        db,
        workspace_id,
        publication_id,
    ):
        calls.append(
            "preflight"
        )

        return SimpleNamespace(
            content_hash=CONTENT_HASH,
        )

    async def create_confirmation(
        *,
        workspace_id,
        publication_id,
        user_id,
        content_hash,
    ):
        calls.append(
            "confirmation"
        )

        return CONFIRMATION

    originals = (
        publications.require_workspace_publish,
        publications.build_publication_meta_dry_run,
        publications.create_publication_confirmation,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.build_publication_meta_dry_run = (
        dry_run
    )
    publications.create_publication_confirmation = (
        create_confirmation
    )

    response = Response()

    try:
        result = (
            await publications
            .issue_publish_confirmation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=response,
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        )
    finally:
        (
            publications.require_workspace_publish,
            publications.build_publication_meta_dry_run,
            publications.create_publication_confirmation,
        ) = originals

    if calls != [
        "authorize",
        "preflight",
        "confirmation",
    ]:
        raise AssertionError(
            "confirmation execution order mismatch"
        )

    if result.confirmation != CONFIRMATION:
        raise AssertionError(
            "confirmation response mismatch"
        )

    if (
        response.headers.get(
            "Cache-Control"
        )
        != "no-store"
    ):
        raise AssertionError(
            "Cache-Control no-store missing"
        )

    if (
        response.headers.get(
            "Pragma"
        )
        != "no-cache"
    ):
        raise AssertionError(
            "Pragma no-cache missing"
        )

    if (
        response.headers.get(
            "Expires"
        )
        != "0"
    ):
        raise AssertionError(
            "Expires zero missing"
        )

    print(
        "Confirmation Cache-Control no-store: PASS"
    )
    print(
        "Confirmation Pragma no-cache: PASS"
    )
    print(
        "Confirmation Expires 0: PASS"
    )
    print(
        "Bearer confirmation printed: NO"
    )
    print(
        "Real Redis calls: NONE"
    )
    print(
        "Real Meta calls: NONE"
    )


asyncio.run(main())
