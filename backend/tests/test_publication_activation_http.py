import asyncio
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import Response

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


HASH = "b" * 64
FAKE_BEARER = "x" * 43


async def main():
    original_auth = (
        publications.require_workspace_publish_activation
    )

    original_dry_run = (
        publications.build_publication_meta_dry_run
    )

    original_create = (
        publications.create_publication_activation
    )

    trace = []

    async def fake_auth(
        db,
        user,
        workspace_id,
    ):
        trace.append(
            "auth"
        )

    async def fake_dry_run(
        db,
        workspace_id,
        publication_id,
    ):
        trace.append(
            "dry-run"
        )

        return SimpleNamespace(
            content_hash=HASH
        )

    async def fake_create(
        *,
        workspace_id,
        publication_id,
        user_id,
        content_hash,
    ):
        trace.append(
            "create"
        )

        if content_hash != HASH:
            raise AssertionError(
                "HTTP activation hash propagation failed"
            )

        return FAKE_BEARER

    try:
        publications.require_workspace_publish_activation = (
            fake_auth
        )

        publications.build_publication_meta_dry_run = (
            fake_dry_run
        )

        publications.create_publication_activation = (
            fake_create
        )

        workspace_id = uuid4()
        publication_id = uuid4()
        user_id = uuid4()

        response = Response()

        result = (
            await publications.create_publication_activation_endpoint(
                workspace_id=workspace_id,
                publication_id=publication_id,
                response=response,
                current_user=SimpleNamespace(
                    id=user_id
                ),
                db=object(),
            )
        )

        if trace != [
            "auth",
            "dry-run",
            "create",
        ]:
            raise AssertionError(
                f"activation endpoint ordering={trace}"
            )

        if (
            result.publication_id
            != publication_id
            or result.activation
            != FAKE_BEARER
            or result.content_hash
            != HASH
        ):
            raise AssertionError(
                "activation HTTP response contract failed"
            )

        if (
            response.headers.get(
                "Cache-Control"
            )
            != "no-store"
        ):
            raise AssertionError(
                "activation Cache-Control missing"
            )

        if (
            response.headers.get(
                "Pragma"
            )
            != "no-cache"
        ):
            raise AssertionError(
                "activation Pragma missing"
            )

        if (
            response.headers.get(
                "Expires"
            )
            != "0"
        ):
            raise AssertionError(
                "activation Expires missing"
            )

        print(
            "Activation HTTP authorization first: PASS"
        )
        print(
            "Activation HTTP dry-run before issuance: PASS"
        )
        print(
            "Activation HTTP exact content hash binding: PASS"
        )
        print(
            "Activation HTTP Cache-Control no-store: PASS"
        )
        print(
            "Activation HTTP Pragma no-cache: PASS"
        )
        print(
            "Activation HTTP Expires 0: PASS"
        )

        #
        # Authorization denial must stop dry-run/issuance.
        #
        trace.clear()

        async def deny_auth(
            db,
            user,
            workspace_id,
        ):
            trace.append(
                "auth"
            )

            raise HTTPException(
                status_code=403,
                detail="denied",
            )

        publications.require_workspace_publish_activation = (
            deny_auth
        )

        try:
            await publications.create_publication_activation_endpoint(
                workspace_id=workspace_id,
                publication_id=publication_id,
                response=Response(),
                current_user=SimpleNamespace(
                    id=user_id
                ),
                db=object(),
            )
        except HTTPException as exc:
            if exc.status_code != 403:
                raise AssertionError(
                    "activation denial wrong HTTP status"
                )
        else:
            raise AssertionError(
                "activation authorization denial failed"
            )

        if trace != [
            "auth",
        ]:
            raise AssertionError(
                "denied activation reached later stages"
            )

        print(
            "Denied activation stops before dry-run: PASS"
        )
        print(
            "Denied activation issuance: NONE"
        )

        #
        # Backend failure must be generic.
        #
        trace.clear()

        publications.require_workspace_publish_activation = (
            fake_auth
        )

        publications.build_publication_meta_dry_run = (
            fake_dry_run
        )

        async def failing_create(
            **kwargs,
        ):
            trace.append(
                "create"
            )

            raise RuntimeError(
                "SECRET_INTERNAL_REDIS_DETAIL"
            )

        publications.create_publication_activation = (
            failing_create
        )

        try:
            await publications.create_publication_activation_endpoint(
                workspace_id=workspace_id,
                publication_id=publication_id,
                response=Response(),
                current_user=SimpleNamespace(
                    id=user_id
                ),
                db=object(),
            )
        except HTTPException as exc:
            if exc.status_code != 503:
                raise AssertionError(
                    "activation backend failure wrong status"
                )

            if (
                "SECRET_INTERNAL_REDIS_DETAIL"
                in str(
                    exc.detail
                )
            ):
                raise AssertionError(
                    "activation backend secret exposed"
                )
        else:
            raise AssertionError(
                "activation backend failure did not fail closed"
            )

        print(
            "Activation backend failure -> HTTP 503: PASS"
        )
        print(
            "Activation backend secret isolation: PASS"
        )

    finally:
        publications.require_workspace_publish_activation = (
            original_auth
        )

        publications.build_publication_meta_dry_run = (
            original_dry_run
        )

        publications.create_publication_activation = (
            original_create
        )


asyncio.run(
    main()
)

print()
print(
    "v0.13E-E-C activation HTTP behavior: PASS"
)
print(
    "Activation bearer printed: NO"
)
print(
    "Real Redis calls: NONE"
)
print(
    "Credential decrypt calls: NONE"
)
print(
    "Real Meta calls: NONE"
)
print(
    "Facebook posts created: NONE"
)
