import asyncio
from types import SimpleNamespace
from uuid import UUID

import app.services.publication_controlled_execution as controlled
from app.services.meta_publishing import (
    MetaPublishResult,
)
from app.services.publication_confirmation import (
    PublicationConfirmationReplay,
)
from app.services.publication_executor import (
    PublicationExecutionOutcomeUnknown,
    PublicationExecutionProviderRejected,
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
STALE_HASH = "b" * 64

CONFIRMATION = (
    "FAKE_CONFIRMATION_VALUE_"
    "NOT_REAL_12345678901234567890"
)


class FakeDB:
    pass


class FakeTransport:
    async def create_page_text_post(
        self,
        *,
        page_id,
        page_access_token,
        message,
    ):
        raise AssertionError(
            "orchestration test must not call "
            "provider transport directly"
        )


async def disabled_case():
    calls = []

    async def preflight(
        *args,
        **kwargs,
    ):
        calls.append(
            "preflight"
        )

    async def consume(
        *args,
        **kwargs,
    ):
        calls.append(
            "consume"
        )

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

    originals = (
        controlled.settings.real_publish_enabled,
        controlled.build_publication_meta_dry_run,
        controlled.consume_and_verify_publication_confirmation,
        controlled.execute_meta_publication_with_transport,
    )

    controlled.settings.real_publish_enabled = False
    controlled.build_publication_meta_dry_run = (
        preflight
    )
    controlled.consume_and_verify_publication_confirmation = (
        consume
    )
    controlled.execute_meta_publication_with_transport = (
        execute
    )

    try:
        try:
            await controlled.execute_confirmed_meta_publication_with_transport(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                confirmation_value=CONFIRMATION,
                expected_content_hash=CONTENT_HASH,
                transport=FakeTransport(),
            )
        except controlled.ControlledPublicationExecutionDisabled:
            pass
        else:
            raise AssertionError(
                "disabled kill switch accepted execution"
            )
    finally:
        (
            controlled.settings.real_publish_enabled,
            controlled.build_publication_meta_dry_run,
            controlled.consume_and_verify_publication_confirmation,
            controlled.execute_meta_publication_with_transport,
        ) = originals

    assert calls == []

    print(
        "Default-OFF kill switch blocks all execution: PASS"
    )
    print(
        "Disabled execution Redis consumption: NONE"
    )
    print(
        "Disabled execution DB/provider activity: NONE"
    )


async def success_case():
    calls = []
    transport = FakeTransport()

    async def preflight(
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

    async def consume(
        *,
        confirmation_value,
        expected_workspace_id,
        expected_publication_id,
        expected_user_id,
        expected_content_hash,
    ):
        assert confirmation_value == CONFIRMATION
        assert expected_workspace_id == WORKSPACE_ID
        assert expected_publication_id == PUBLICATION_ID
        assert expected_user_id == USER_ID
        assert expected_content_hash == CONTENT_HASH

        calls.append(
            "consume"
        )

        return SimpleNamespace(
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            user_id=USER_ID,
            content_hash=CONTENT_HASH,
        )

    async def execute(
        *,
        db,
        workspace_id,
        publication_id,
        triggered_by_user_id,
        transport: object,
    ):
        assert workspace_id == WORKSPACE_ID
        assert publication_id == PUBLICATION_ID
        assert triggered_by_user_id == USER_ID
        assert transport is transport_object

        calls.append(
            "execute"
        )

        return MetaPublishResult(
            provider_post_id=(
                "mock_page_mock_post"
            ),
            provider_permalink=None,
        )

    transport_object = transport

    originals = (
        controlled.settings.real_publish_enabled,
        controlled.build_publication_meta_dry_run,
        controlled.consume_and_verify_publication_confirmation,
        controlled.execute_meta_publication_with_transport,
    )

    controlled.settings.real_publish_enabled = True
    controlled.build_publication_meta_dry_run = (
        preflight
    )
    controlled.consume_and_verify_publication_confirmation = (
        consume
    )
    controlled.execute_meta_publication_with_transport = (
        execute
    )

    try:
        result = (
            await controlled
            .execute_confirmed_meta_publication_with_transport(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                confirmation_value=CONFIRMATION,
                expected_content_hash=CONTENT_HASH,
                transport=transport,
            )
        )
    finally:
        (
            controlled.settings.real_publish_enabled,
            controlled.build_publication_meta_dry_run,
            controlled.consume_and_verify_publication_confirmation,
            controlled.execute_meta_publication_with_transport,
        ) = originals

    assert calls == [
        "preflight",
        "consume",
        "execute",
    ]

    assert (
        result.provider_post_id
        == "mock_page_mock_post"
    )

    print(
        "Controlled execution order "
        "preflight->consume->executor: PASS"
    )
    print(
        "Triggering operator propagated: PASS"
    )
    print(
        "Injected transport propagated: PASS"
    )


async def stale_hash_case():
    calls = []

    async def preflight(
        *args,
        **kwargs,
    ):
        calls.append(
            "preflight"
        )

        return SimpleNamespace(
            content_hash=CONTENT_HASH,
        )

    async def consume(
        *args,
        **kwargs,
    ):
        calls.append(
            "consume"
        )

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

    originals = (
        controlled.settings.real_publish_enabled,
        controlled.build_publication_meta_dry_run,
        controlled.consume_and_verify_publication_confirmation,
        controlled.execute_meta_publication_with_transport,
    )

    controlled.settings.real_publish_enabled = True
    controlled.build_publication_meta_dry_run = (
        preflight
    )
    controlled.consume_and_verify_publication_confirmation = (
        consume
    )
    controlled.execute_meta_publication_with_transport = (
        execute
    )

    try:
        try:
            await controlled.execute_confirmed_meta_publication_with_transport(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                confirmation_value=CONFIRMATION,
                expected_content_hash=STALE_HASH,
                transport=FakeTransport(),
            )
        except controlled.ControlledPublicationContentHashMismatch:
            pass
        else:
            raise AssertionError(
                "stale content hash accepted"
            )
    finally:
        (
            controlled.settings.real_publish_enabled,
            controlled.build_publication_meta_dry_run,
            controlled.consume_and_verify_publication_confirmation,
            controlled.execute_meta_publication_with_transport,
        ) = originals

    assert calls == [
        "preflight",
    ]

    print(
        "Stale expected content hash blocked: PASS"
    )
    print(
        "Stale hash confirmation not consumed: PASS"
    )
    print(
        "Stale hash executor activity: NONE"
    )


async def confirmation_replay_case():
    calls = []
    consume_count = 0

    async def preflight(
        *args,
        **kwargs,
    ):
        calls.append(
            "preflight"
        )

        return SimpleNamespace(
            content_hash=CONTENT_HASH,
        )

    async def consume(
        *args,
        **kwargs,
    ):
        nonlocal consume_count

        consume_count += 1
        calls.append(
            "consume"
        )

        if consume_count > 1:
            raise PublicationConfirmationReplay(
                "already used"
            )

        return SimpleNamespace()

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

        return MetaPublishResult(
            provider_post_id=(
                "mock_page_first_execution"
            ),
            provider_permalink=None,
        )

    originals = (
        controlled.settings.real_publish_enabled,
        controlled.build_publication_meta_dry_run,
        controlled.consume_and_verify_publication_confirmation,
        controlled.execute_meta_publication_with_transport,
    )

    controlled.settings.real_publish_enabled = True
    controlled.build_publication_meta_dry_run = (
        preflight
    )
    controlled.consume_and_verify_publication_confirmation = (
        consume
    )
    controlled.execute_meta_publication_with_transport = (
        execute
    )

    try:
        await controlled.execute_confirmed_meta_publication_with_transport(
            db=FakeDB(),
            workspace_id=WORKSPACE_ID,
            publication_id=PUBLICATION_ID,
            user_id=USER_ID,
            confirmation_value=CONFIRMATION,
            expected_content_hash=CONTENT_HASH,
            transport=FakeTransport(),
        )

        try:
            await controlled.execute_confirmed_meta_publication_with_transport(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                confirmation_value=CONFIRMATION,
                expected_content_hash=CONTENT_HASH,
                transport=FakeTransport(),
            )
        except controlled.ControlledPublicationConfirmationRejected:
            pass
        else:
            raise AssertionError(
                "confirmation replay reached executor"
            )
    finally:
        (
            controlled.settings.real_publish_enabled,
            controlled.build_publication_meta_dry_run,
            controlled.consume_and_verify_publication_confirmation,
            controlled.execute_meta_publication_with_transport,
        ) = originals

    assert calls.count(
        "execute"
    ) == 1

    print(
        "Confirmation replay blocked before executor: PASS"
    )
    print(
        "Replay provider execution count remains one: PASS"
    )


async def provider_rejection_case():
    calls = []

    async def preflight(
        *args,
        **kwargs,
    ):
        return SimpleNamespace(
            content_hash=CONTENT_HASH,
        )

    async def consume(
        *args,
        **kwargs,
    ):
        calls.append(
            "consume"
        )

        return SimpleNamespace()

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

        raise PublicationExecutionProviderRejected(
            "Meta publishing request was rejected"
        )

    originals = (
        controlled.settings.real_publish_enabled,
        controlled.build_publication_meta_dry_run,
        controlled.consume_and_verify_publication_confirmation,
        controlled.execute_meta_publication_with_transport,
    )

    controlled.settings.real_publish_enabled = True
    controlled.build_publication_meta_dry_run = (
        preflight
    )
    controlled.consume_and_verify_publication_confirmation = (
        consume
    )
    controlled.execute_meta_publication_with_transport = (
        execute
    )

    try:
        try:
            await controlled.execute_confirmed_meta_publication_with_transport(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                confirmation_value=CONFIRMATION,
                expected_content_hash=CONTENT_HASH,
                transport=FakeTransport(),
            )
        except PublicationExecutionProviderRejected:
            pass
        else:
            raise AssertionError(
                "provider rejection was swallowed"
            )
    finally:
        (
            controlled.settings.real_publish_enabled,
            controlled.build_publication_meta_dry_run,
            controlled.consume_and_verify_publication_confirmation,
            controlled.execute_meta_publication_with_transport,
        ) = originals

    assert calls == [
        "consume",
        "execute",
    ]

    print(
        "Definite provider rejection propagation: PASS"
    )


async def outcome_unknown_case():
    calls = []

    async def preflight(
        *args,
        **kwargs,
    ):
        return SimpleNamespace(
            content_hash=CONTENT_HASH,
        )

    async def consume(
        *args,
        **kwargs,
    ):
        calls.append(
            "consume"
        )

        return SimpleNamespace()

    async def execute(
        *args,
        **kwargs,
    ):
        calls.append(
            "execute"
        )

        raise PublicationExecutionOutcomeUnknown(
            "Meta publishing outcome is unknown; "
            "manual reconciliation required"
        )

    originals = (
        controlled.settings.real_publish_enabled,
        controlled.build_publication_meta_dry_run,
        controlled.consume_and_verify_publication_confirmation,
        controlled.execute_meta_publication_with_transport,
    )

    controlled.settings.real_publish_enabled = True
    controlled.build_publication_meta_dry_run = (
        preflight
    )
    controlled.consume_and_verify_publication_confirmation = (
        consume
    )
    controlled.execute_meta_publication_with_transport = (
        execute
    )

    try:
        try:
            await controlled.execute_confirmed_meta_publication_with_transport(
                db=FakeDB(),
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                user_id=USER_ID,
                confirmation_value=CONFIRMATION,
                expected_content_hash=CONTENT_HASH,
                transport=FakeTransport(),
            )
        except PublicationExecutionOutcomeUnknown as exc:
            assert (
                "manual reconciliation"
                in str(exc)
            )
        else:
            raise AssertionError(
                "outcome-unknown was swallowed"
            )
    finally:
        (
            controlled.settings.real_publish_enabled,
            controlled.build_publication_meta_dry_run,
            controlled.consume_and_verify_publication_confirmation,
            controlled.execute_meta_publication_with_transport,
        ) = originals

    assert calls == [
        "consume",
        "execute",
    ]

    print(
        "Outcome-unknown propagation: PASS"
    )
    print(
        "Outcome-unknown automatic retry introduced: NO"
    )


async def main():
    await disabled_case()
    await success_case()
    await stale_hash_case()
    await confirmation_replay_case()
    await provider_rejection_case()
    await outcome_unknown_case()

    print()
    print(
        "v0.13E-C-A controlled execution orchestration: PASS"
    )
    print(
        "Concrete Meta transport construction: NONE"
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
