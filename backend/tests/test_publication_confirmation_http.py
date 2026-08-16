from fastapi import Response
import asyncio
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException

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
from app.services.publication_workflow import (
    PublicationStateError,
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

FAKE_CONFIRMATION = (
    "FAKE_CONFIRMATION_VALUE_"
    "NOT_A_REAL_SECRET_1234567890"
)


class FakeDB:
    async def commit(self):
        raise AssertionError(
            "confirmation endpoint must not commit DB"
        )

    async def rollback(self):
        raise AssertionError(
            "confirmation endpoint must not rollback DB"
        )


async def success_case():
    calls = []

    async def authorize(
        db,
        user,
        workspace_id,
    ):
        assert workspace_id == WORKSPACE_ID
        assert user.id == USER_ID
        calls.append(
            "authorize"
        )

    async def dry_run(
        db,
        workspace_id,
        publication_id,
    ):
        assert workspace_id == WORKSPACE_ID
        assert publication_id == PUBLICATION_ID

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
        assert workspace_id == WORKSPACE_ID
        assert publication_id == PUBLICATION_ID
        assert user_id == USER_ID
        assert content_hash == CONTENT_HASH

        calls.append(
            "confirmation"
        )

        return FAKE_CONFIRMATION

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

    try:
        response = (
            await publications
            .issue_publish_confirmation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=Response(),
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

    assert calls == [
        "authorize",
        "preflight",
        "confirmation",
    ]

    assert (
        response.publication_id
        == PUBLICATION_ID
    )

    assert (
        response.confirmation
        == FAKE_CONFIRMATION
    )

    assert (
        response.expires_in
        == publications
        .PUBLICATION_CONFIRMATION_TTL_SECONDS
    )

    assert (
        response.content_hash
        == CONTENT_HASH
    )

    #
    # Do not print confirmation_value.
    #
    print(
        "Confirmation HTTP authorization/preflight/order: PASS"
    )
    print(
        "Confirmation HTTP response contract: PASS"
    )
    print(
        "Confirmation HTTP DB mutation: NONE"
    )


async def permission_failure_case():
    dry_run_called = False
    confirmation_called = False

    async def deny(
        db,
        user,
        workspace_id,
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Insufficient publishing permission"
            ),
        )

    async def dry_run(
        *args,
        **kwargs,
    ):
        nonlocal dry_run_called
        dry_run_called = True

    async def create_confirmation(
        *args,
        **kwargs,
    ):
        nonlocal confirmation_called
        confirmation_called = True

    originals = (
        publications.require_workspace_publish,
        publications.build_publication_meta_dry_run,
        publications.create_publication_confirmation,
    )

    publications.require_workspace_publish = deny
    publications.build_publication_meta_dry_run = (
        dry_run
    )
    publications.create_publication_confirmation = (
        create_confirmation
    )

    try:
        try:
            await publications.issue_publish_confirmation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError(
                "publish permission failure accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.build_publication_meta_dry_run,
            publications.create_publication_confirmation,
        ) = originals

    assert dry_run_called is False
    assert confirmation_called is False

    print(
        "Denied publisher cannot reach preflight: PASS"
    )
    print(
        "Denied publisher cannot create confirmation: PASS"
    )


async def preflight_failure_case():
    confirmation_called = False

    async def authorize(
        *args,
        **kwargs,
    ):
        return None

    async def dry_run(
        *args,
        **kwargs,
    ):
        raise PublicationStateError(
            "Publication is not approved"
        )

    async def create_confirmation(
        *args,
        **kwargs,
    ):
        nonlocal confirmation_called
        confirmation_called = True

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

    try:
        try:
            await publications.issue_publish_confirmation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError(
                "invalid Publication preflight accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.build_publication_meta_dry_run,
            publications.create_publication_confirmation,
        ) = originals

    assert confirmation_called is False

    print(
        "Invalid Publication cannot create confirmation: PASS"
    )


async def confirmation_backend_failure_case():
    async def authorize(
        *args,
        **kwargs,
    ):
        return None

    async def dry_run(
        *args,
        **kwargs,
    ):
        return SimpleNamespace(
            content_hash=CONTENT_HASH,
        )

    async def create_confirmation(
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "SECRET_REDIS_INTERNAL_DETAIL"
        )

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

    try:
        try:
            await publications.issue_publish_confirmation_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 503

            detail = str(
                exc.detail
            )

            assert (
                "SECRET_REDIS_INTERNAL_DETAIL"
                not in detail
            )

            assert (
                detail
                == (
                    "Publication confirmation "
                    "could not be created"
                )
            )
        else:
            raise AssertionError(
                "confirmation backend failure accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.build_publication_meta_dry_run,
            publications.create_publication_confirmation,
        ) = originals

    print(
        "Confirmation backend failure fails closed: PASS"
    )
    print(
        "Confirmation backend error secret isolation: PASS"
    )


async def main():
    await success_case()
    await permission_failure_case()
    await preflight_failure_case()
    await confirmation_backend_failure_case()

    print()
    print(
        "v0.13E-B confirmation HTTP behavior tests: PASS"
    )
    print(
        "Real Redis calls: NONE"
    )
    print(
        "OAuth credential decrypt calls: NONE"
    )
    print(
        "Real Meta network calls: NONE"
    )
    print(
        "Facebook posts created: NONE"
    )


asyncio.run(main())
