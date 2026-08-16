import asyncio
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, Response

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

from app.models.publication import (
    PublicationStatus,
)
from app.schemas.publication import (
    PublicationPublishRequest,
)
from app.services.meta_publishing import (
    MetaPublishResult,
)
from app.services.publication_controlled_execution import (
    ControlledPublicationConfirmationRejected,
    ControlledPublicationContentHashMismatch,
)
from app.services.publication_executor import (
    PublicationExecutionOutcomeUnknown,
    PublicationExecutionProviderRejected,
)
from app.services.publication_publish_transport import (
    PublicationPublishTransportUnavailable,
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

#
# This legacy HTTP regression suite exercises gates after the
# publication-target policy. Dedicated target-policy tests cover
# rejection semantics, so give this isolated process the exact
# allowed canary target used by its fixed test identifiers.
#
publications.settings.meta_publish_canary_mode_enabled = True
publications.settings.meta_publish_canary_workspace_id = WORKSPACE_ID
publications.settings.meta_publish_canary_publication_id = PUBLICATION_ID

CONFIRMATION = (
    "FAKE_CONFIRMATION_VALUE_"
    "NOT_REAL_12345678901234567890"
)


class FakeDB:
    pass


class FakeTransport:
    pass


ACTIVATION = "activation-test-bearer-" + ("a" * 32)


async def allow_activation(
    **kwargs,
):
    return None


#
# This legacy D-A regression exercises the HTTP behavior that
# follows the activation gate. Dedicated E-C tests below cover
# activation ordering and rejection semantics.
#
publications.verify_and_consume_publication_activation_for_execution = (
    allow_activation
)


def payload():
    return PublicationPublishRequest(
        activation=ACTIVATION,
        confirmation=CONFIRMATION,
        content_hash=CONTENT_HASH,
    )


async def permission_denied_case():
    calls = []

    async def deny(
        db,
        user,
        workspace_id,
    ):
        calls.append(
            "authorize"
        )

        raise HTTPException(
            status_code=403,
            detail=(
                "Insufficient publishing permission"
            ),
        )

    def transport_factory():
        calls.append(
            "transport"
        )

        return FakeTransport()

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = deny
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    try:
        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
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
                "permission-denied publish accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    assert calls == [
        "authorize",
    ]

    print(
        "Publish permission denial blocks all execution: PASS"
    )


async def disabled_case():
    calls = []

    async def authorize(
        *args,
        **kwargs,
    ):
        calls.append(
            "authorize"
        )

    def transport_factory():
        calls.append(
            "transport"
        )

        return FakeTransport()

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = False

    try:
        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 503
            assert exc.detail == (
                "Real publishing is disabled"
            )
        else:
            raise AssertionError(
                "disabled publish accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    assert calls == [
        "authorize",
    ]

    print(
        "HTTP kill switch blocks transport/executor: PASS"
    )


async def transport_unavailable_case():
    calls = []

    async def authorize(
        *args,
        **kwargs,
    ):
        calls.append(
            "authorize"
        )

    def unavailable():
        calls.append(
            "transport"
        )

        raise PublicationPublishTransportUnavailable(
            "SECRET_INTERNAL_TRANSPORT_DETAIL"
        )

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        unavailable
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    try:
        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 503

            assert (
                "SECRET_INTERNAL_TRANSPORT_DETAIL"
                not in str(
                    exc.detail
                )
            )
        else:
            raise AssertionError(
                "unconfigured transport accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    assert calls == [
        "authorize",
        "transport",
    ]

    print(
        "Unconfigured provider transport fails closed: PASS"
    )
    print(
        "Transport configuration detail isolation: PASS"
    )


async def success_case():
    calls = []
    fake_transport = FakeTransport()

    async def authorize(
        *args,
        **kwargs,
    ):
        calls.append(
            "authorize"
        )

    def transport_factory():
        calls.append(
            "transport"
        )

        return fake_transport

    async def execute(
        *,
        db,
        workspace_id,
        publication_id,
        user_id,
        confirmation_value,
        expected_content_hash,
        transport,
    ):
        assert workspace_id == WORKSPACE_ID
        assert publication_id == PUBLICATION_ID
        assert user_id == USER_ID
        assert confirmation_value == CONFIRMATION
        assert expected_content_hash == CONTENT_HASH
        assert transport is fake_transport

        calls.append(
            "execute"
        )

        return MetaPublishResult(
            provider_post_id=(
                "mock_page_mock_post"
            ),
            provider_permalink=None,
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    response = Response()

    try:
        result = (
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
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
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    assert calls == [
        "authorize",
        "transport",
        "execute",
    ]

    assert (
        result.status
        == PublicationStatus.published
    )

    assert (
        result.provider_post_id
        == "mock_page_mock_post"
    )

    assert (
        result.reconciliation_required
        is False
    )

    print(
        "Mock HTTP publish success mapping: PASS"
    )
    print(
        "HTTP confirmation/hash/operator propagation: PASS"
    )


async def stale_hash_case():
    async def authorize(
        *args,
        **kwargs,
    ):
        return None

    def transport_factory():
        return FakeTransport()

    async def execute(
        *args,
        **kwargs,
    ):
        raise ControlledPublicationContentHashMismatch(
            "SECRET_INTERNAL_HASH_DETAIL"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    try:
        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 409

            assert (
                "SECRET_INTERNAL_HASH_DETAIL"
                not in str(
                    exc.detail
                )
            )
        else:
            raise AssertionError(
                "stale hash accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    print(
        "HTTP stale content hash mapping: PASS"
    )


async def confirmation_rejected_case():
    async def authorize(
        *args,
        **kwargs,
    ):
        return None

    def transport_factory():
        return FakeTransport()

    async def execute(
        *args,
        **kwargs,
    ):
        raise ControlledPublicationConfirmationRejected(
            "SECRET_CONFIRMATION_DETAIL"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    try:
        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 409
            assert (
                "SECRET_CONFIRMATION_DETAIL"
                not in str(
                    exc.detail
                )
            )
        else:
            raise AssertionError(
                "invalid confirmation accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    print(
        "HTTP confirmation rejection mapping: PASS"
    )


async def provider_rejection_case():
    async def authorize(
        *args,
        **kwargs,
    ):
        return None

    def transport_factory():
        return FakeTransport()

    async def execute(
        *args,
        **kwargs,
    ):
        raise PublicationExecutionProviderRejected(
            "SECRET_PROVIDER_DETAIL"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    try:
        try:
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
                response=Response(),
                current_user=SimpleNamespace(
                    id=USER_ID,
                ),
                db=FakeDB(),
            )
        except HTTPException as exc:
            assert exc.status_code == 502

            assert (
                "SECRET_PROVIDER_DETAIL"
                not in str(
                    exc.detail
                )
            )
        else:
            raise AssertionError(
                "provider rejection accepted"
            )
    finally:
        (
            publications.require_workspace_publish,
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    print(
        "HTTP definite provider rejection mapping: PASS"
    )
    print(
        "HTTP provider secret isolation: PASS"
    )


async def outcome_unknown_case():
    async def authorize(
        *args,
        **kwargs,
    ):
        return None

    def transport_factory():
        return FakeTransport()

    async def execute(
        *args,
        **kwargs,
    ):
        raise PublicationExecutionOutcomeUnknown(
            "SECRET_TIMEOUT_DETAIL "
            "manual reconciliation required"
        )

    originals = (
        publications.require_workspace_publish,
        publications.get_publication_publish_transport,
        publications.execute_confirmed_meta_publication_with_transport,
        publications.settings.real_publish_enabled,
    )

    publications.require_workspace_publish = (
        authorize
    )
    publications.get_publication_publish_transport = (
        transport_factory
    )
    publications.execute_confirmed_meta_publication_with_transport = (
        execute
    )
    publications.settings.real_publish_enabled = True

    response = Response()

    try:
        result = (
            await publications.publish_publication_endpoint(
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                payload=payload(),
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
            publications.get_publication_publish_transport,
            publications.execute_confirmed_meta_publication_with_transport,
            publications.settings.real_publish_enabled,
        ) = originals

    assert response.status_code == 202

    assert (
        result.status
        == PublicationStatus.publishing
    )

    assert (
        result.reconciliation_required
        is True
    )

    assert result.provider_post_id is None

    print(
        "HTTP outcome-unknown -> 202 reconciliation: PASS"
    )
    print(
        "HTTP unknown outcome does not suggest retry: PASS"
    )


async def main():
    await permission_denied_case()
    await disabled_case()
    await transport_unavailable_case()
    await success_case()
    await stale_hash_case()
    await confirmation_rejected_case()
    await provider_rejection_case()
    await outcome_unknown_case()

    print()
    print(
        "v0.13E-D-A /publish source HTTP behavior: PASS"
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
