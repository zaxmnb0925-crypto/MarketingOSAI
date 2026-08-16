import asyncio
import hashlib
import os
from _integration_run_identity import integration_token, integration_uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.models.publication import (
    Publication,
    PublicationStatus,
)
from app.models.publication_reconciliation import (
    PublicationReconciliationDecision as Decision,
)
from app.services.publication_reconciliation import (
    PublicationReconciliationIdempotencyConflict,
    reconcile_publication,
)
from app.services.publication_workflow import (
    PublicationStateError,
)


WORKSPACE_ID = integration_uuid("reconciliation-workspace")
USER_ID = integration_uuid("reconciliation-user")
PUBLICATION_ID = integration_uuid("reconciliation-publication")
ROLLBACK_PUBLICATION_ID = integration_uuid("reconciliation-rollback-publication")
RUN_TOKEN = integration_token("reconciliation")

CONTENT = "v0.13G real PostgreSQL reconciliation integration"

CONTENT_HASH = hashlib.sha256(
    CONTENT.encode("utf-8")
).hexdigest()


DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

Session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def setup_fixture():
    async with Session.begin() as db:
        await db.execute(
            text(
                """
                DELETE FROM workspaces
                WHERE id = :workspace_id
                """
            ),
            {
                "workspace_id": WORKSPACE_ID,
            },
        )

        await db.execute(
            text(
                """
                DELETE FROM users
                WHERE id = :user_id
                """
            ),
            {
                "user_id": USER_ID,
            },
        )

        await db.execute(
            text(
                """
                INSERT INTO users (
                    id,
                    email,
                    is_active,
                    created_at
                )
                VALUES (
                    :user_id,
                    :email,
                    true,
                    now()
                )
                """
            ),
            {
                "user_id": USER_ID,
                "email": RUN_TOKEN + "@example.invalid",
            },
        )

        await db.execute(
            text(
                """
                INSERT INTO workspaces (
                    id,
                    name,
                    slug,
                    created_at
                )
                VALUES (
                    :workspace_id,
                    :workspace_name,
                    :workspace_slug,
                    now()
                )
                """
            ),
            {
                "workspace_id": WORKSPACE_ID,
                "workspace_name": RUN_TOKEN,
                "workspace_slug": RUN_TOKEN,
            },
        )

        for publication_id, suffix in (
            (
                PUBLICATION_ID,
                "main",
            ),
            (
                ROLLBACK_PUBLICATION_ID,
                "rollback",
            ),
        ):
            await db.execute(
                text(
                    """
                    INSERT INTO publications (
                        id,
                        workspace_id,
                        created_by_user_id,
                        status,
                        platform,
                        target_account_id,
                        content_snapshot,
                        content_hash,
                        idempotency_key,
                        publish_attempts,
                        provider_post_id,
                        provider_permalink,
                        last_error,
                        published_at,
                        created_at,
                        updated_at,
                        publish_triggered_by_user_id,
                        publish_triggered_at,
                        reconciliation_required
                    )
                    VALUES (
                        :publication_id,
                        :workspace_id,
                        :user_id,
                        'publishing',
                        'facebook',
                        :target_account_id,
                        :content_snapshot,
                        :content_hash,
                        :idempotency_key,
                        1,
                        NULL,
                        NULL,
                        'Publishing outcome is unknown; manual reconciliation required',
                        NULL,
                        now(),
                        now(),
                        :user_id,
                        now(),
                        true
                    )
                    """
                ),
                {
                    "publication_id": publication_id,
                    "workspace_id": WORKSPACE_ID,
                    "user_id": USER_ID,
                    "target_account_id": (
                        "integration-" + suffix
                    ),
                    "content_snapshot": CONTENT,
                    "content_hash": CONTENT_HASH,
                    "idempotency_key": (
                        "integration-publication-" + suffix
                    ),
                },
            )


async def cleanup_fixture():
    async with Session.begin() as db:
        await db.execute(
            text(
                """
                DELETE FROM workspaces
                WHERE id = :workspace_id
                """
            ),
            {
                "workspace_id": WORKSPACE_ID,
            },
        )

        await db.execute(
            text(
                """
                DELETE FROM users
                WHERE id = :user_id
                """
            ),
            {
                "user_id": USER_ID,
            },
        )


async def reconciliation_count(
    publication_id,
):
    async with Session() as db:
        result = await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM publication_reconciliations
                WHERE publication_id = :publication_id
                """
            ),
            {
                "publication_id": publication_id,
            },
        )

        return result.scalar_one()


async def main_publication_state():
    async with Session() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    status::text,
                    reconciliation_required,
                    publish_attempts,
                    provider_post_id
                FROM publications
                WHERE id = :publication_id
                """
            ),
            {
                "publication_id": PUBLICATION_ID,
            },
        )

        return result.one()


async def concurrent_idempotent_replay_test():
    #
    # Transaction 1 runs the real service and keeps its
    # SELECT ... FOR UPDATE lock open after flush.
    #
    async with Session() as db1:
        reconciliation_1, publication_1 = (
            await reconcile_publication(
                db1,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.remain_unresolved,
                publish_attempt_number=1,
                idempotency_key="concurrent-key",
                evidence_note=(
                    "Independent evidence remains inconclusive."
                ),
            )
        )

        reconciliation_1_id = reconciliation_1.id

        assert (
            publication_1.status
            == PublicationStatus.publishing
        )

        assert (
            publication_1.reconciliation_required
            is True
        )

        async def contender():
            async with Session() as db2:
                reconciliation_2, publication_2 = (
                    await reconcile_publication(
                        db2,
                        workspace_id=WORKSPACE_ID,
                        publication_id=PUBLICATION_ID,
                        operator_user_id=USER_ID,
                        decision=Decision.remain_unresolved,
                        publish_attempt_number=1,
                        idempotency_key="concurrent-key",
                        evidence_note=(
                            "Independent evidence remains inconclusive."
                        ),
                    )
                )

                await db2.commit()

                return (
                    reconciliation_2.id,
                    publication_2.status,
                    publication_2.reconciliation_required,
                )

        task = asyncio.create_task(
            contender()
        )

        #
        # Contender must block on the Publication row while
        # transaction 1 owns the FOR UPDATE lock.
        #
        await asyncio.sleep(0.35)

        if task.done():
            raise AssertionError(
                "concurrent reconciliation bypassed row lock"
            )

        print(
            "Concurrent reconciliation waits on row lock: PASS"
        )

        await db1.commit()

        reconciliation_2_id, status_2, required_2 = (
            await asyncio.wait_for(
                task,
                timeout=5,
            )
        )

        assert (
            reconciliation_2_id
            == reconciliation_1_id
        )

        assert (
            status_2
            == PublicationStatus.publishing
        )

        assert required_2 is True

    count = await reconciliation_count(
        PUBLICATION_ID
    )

    assert count == 1

    print(
        "Concurrent exact replay serialized to one audit row: PASS"
    )


async def idempotency_conflict_test():
    async with Session() as db:
        try:
            await reconcile_publication(
                db,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.remain_unresolved,
                publish_attempt_number=1,
                idempotency_key="concurrent-key",
                evidence_note=(
                    "Different evidence must conflict."
                ),
            )
        except PublicationReconciliationIdempotencyConflict:
            await db.rollback()
        else:
            raise AssertionError(
                "different payload reused idempotency key"
            )

    assert (
        await reconciliation_count(
            PUBLICATION_ID
        )
        == 1
    )

    print(
        "Real PostgreSQL idempotency conflict: PASS"
    )


async def attempt_binding_test():
    async with Session() as db:
        try:
            await reconcile_publication(
                db,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.remain_unresolved,
                publish_attempt_number=2,
                idempotency_key="wrong-attempt",
                evidence_note=(
                    "Stale attempt must not reconcile."
                ),
            )
        except PublicationStateError:
            await db.rollback()
        else:
            raise AssertionError(
                "stale publish attempt reconciled"
            )

    assert (
        await reconciliation_count(
            PUBLICATION_ID
        )
        == 1
    )

    print(
        "Real PostgreSQL attempt binding: PASS"
    )


async def terminal_publish_test():
    async with Session() as db:
        reconciliation, publication = (
            await reconcile_publication(
                db,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.confirmed_published,
                publish_attempt_number=1,
                idempotency_key="terminal-published",
                evidence_note=(
                    "Provider post independently verified."
                ),
                provider_post_id=(
                    "integration-provider-post"
                ),
                provider_permalink=None,
            )
        )

        terminal_reconciliation_id = (
            reconciliation.id
        )

        assert (
            publication.status
            == PublicationStatus.published
        )

        assert (
            publication.reconciliation_required
            is False
        )

        assert (
            publication.publish_attempts
            == 1
        )

        await db.commit()

    state = await main_publication_state()

    assert state[0] == "published"
    assert state[1] is False
    assert state[2] == 1
    assert (
        state[3]
        == "integration-provider-post"
    )

    assert (
        await reconciliation_count(
            PUBLICATION_ID
        )
        == 2
    )

    print(
        "Confirmed published transaction persisted atomically: PASS"
    )

    #
    # Exact replay must continue to work after terminalization.
    #
    async with Session() as db:
        replay, publication = (
            await reconcile_publication(
                db,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.confirmed_published,
                publish_attempt_number=1,
                idempotency_key="terminal-published",
                evidence_note=(
                    "Provider post independently verified."
                ),
                provider_post_id=(
                    "integration-provider-post"
                ),
                provider_permalink=None,
            )
        )

        assert (
            replay.id
            == terminal_reconciliation_id
        )

        assert (
            publication.status
            == PublicationStatus.published
        )

        await db.commit()

    assert (
        await reconciliation_count(
            PUBLICATION_ID
        )
        == 2
    )

    print(
        "Terminal exact replay remains idempotent: PASS"
    )

    #
    # A new reconciliation key after terminalization
    # must be rejected.
    #
    async with Session() as db:
        try:
            await reconcile_publication(
                db,
                workspace_id=WORKSPACE_ID,
                publication_id=PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.confirmed_failed,
                publish_attempt_number=1,
                idempotency_key="post-terminal-new-key",
                evidence_note=(
                    "Must not alter terminal result."
                ),
            )
        except PublicationStateError:
            await db.rollback()
        else:
            raise AssertionError(
                "new reconciliation accepted after terminal state"
            )

    print(
        "New reconciliation after terminalization rejected: PASS"
    )


async def rollback_atomicity_test():
    async with Session() as db:
        reconciliation, publication = (
            await reconcile_publication(
                db,
                workspace_id=WORKSPACE_ID,
                publication_id=ROLLBACK_PUBLICATION_ID,
                operator_user_id=USER_ID,
                decision=Decision.confirmed_failed,
                publish_attempt_number=1,
                idempotency_key="rollback-test",
                evidence_note=(
                    "Transaction intentionally rolled back."
                ),
            )
        )

        assert reconciliation.id is not None
        assert (
            publication.status
            == PublicationStatus.failed
        )
        assert (
            publication.reconciliation_required
            is False
        )

        #
        # Caller owns transaction boundary.
        #
        await db.rollback()

    async with Session() as db:
        result = await db.execute(
            text(
                """
                SELECT
                    status::text,
                    reconciliation_required,
                    publish_attempts
                FROM publications
                WHERE id = :publication_id
                """
            ),
            {
                "publication_id": ROLLBACK_PUBLICATION_ID,
            },
        )

        state = result.one()

        audit_result = await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM publication_reconciliations
                WHERE publication_id = :publication_id
                """
            ),
            {
                "publication_id": ROLLBACK_PUBLICATION_ID,
            },
        )

        audit_count = (
            audit_result.scalar_one()
        )

    assert state[0] == "publishing"
    assert state[1] is True
    assert state[2] == 1
    assert audit_count == 0

    print(
        "Caller rollback restores Publication and audit together: PASS"
    )


async def run():
    await setup_fixture()

    try:
        await concurrent_idempotent_replay_test()
        await idempotency_conflict_test()
        await attempt_binding_test()
        await terminal_publish_test()
        await rollback_atomicity_test()

        print()
        print(
            "Real PostgreSQL reconciliation service integration: FULL PASS"
        )
        print(
            "Provider/Meta execution invoked: NO"
        )

    finally:
        await cleanup_fixture()
        await engine.dispose()


asyncio.run(
    run()
)
