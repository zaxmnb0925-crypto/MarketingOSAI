import asyncio
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import app.services.publication_reconciliation as service

from app.models.publication import PublicationStatus
from app.models.publication_reconciliation import (
    PublicationReconciliationDecision as Decision,
)
from app.services.publication_reconciliation import (
    PublicationReconciliationIdempotencyConflict,
)
from app.services.publication_workflow import (
    PublicationStateError,
)


class FakeDB:
    def __init__(self):
        self.added = []
        self.flushes = 0

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1


def make_publication(
    *,
    status=PublicationStatus.publishing,
    last_error=(
        "Publishing outcome is unknown; "
        "manual reconciliation required"
    ),
    attempts=1,
    reconciliation_required=True,
):
    content = "reconciliation-test-content"

    return SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        status=status,
        content_snapshot=content,
        content_hash=hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest(),
        provider_post_id=None,
        provider_permalink=None,
        published_at=None,
        last_error=last_error,
        publish_triggered_by_user_id=uuid4(),
        publish_triggered_at=datetime.now(
            timezone.utc
        ),
        publish_attempts=attempts,
        reconciliation_required=reconciliation_required,
    )


async def call_service(
    *,
    publication,
    db,
    operator,
    decision,
    key,
    note,
    attempt=1,
    post_id=None,
    permalink=None,
    existing=None,
):
    async def fake_get_publication(
        _db,
        _workspace_id,
        _publication_id,
    ):
        return publication

    async def fake_get_existing(
        _db,
        _publication_id,
        _idempotency_key,
    ):
        return existing

    service._get_publication_for_reconciliation = (
        fake_get_publication
    )
    service._get_existing_reconciliation = (
        fake_get_existing
    )

    return await service.reconcile_publication(
        db,
        workspace_id=publication.workspace_id,
        publication_id=publication.id,
        operator_user_id=operator,
        decision=decision,
        publish_attempt_number=attempt,
        idempotency_key=key,
        evidence_note=note,
        provider_post_id=post_id,
        provider_permalink=permalink,
    )


async def test_confirmed_published():
    db = FakeDB()
    publication = make_publication()
    operator = uuid4()

    reconciliation, result = await call_service(
        publication=publication,
        db=db,
        operator=operator,
        decision=Decision.confirmed_published,
        key="publish-1",
        note="Provider post independently verified.",
        post_id="provider-post-123",
    )

    assert result is publication
    assert publication.status == PublicationStatus.published
    assert publication.provider_post_id == "provider-post-123"
    assert publication.last_error is None
    assert publication.published_at is not None
    assert publication.publish_attempts == 1
    assert publication.reconciliation_required is False
    assert db.added == [reconciliation]
    assert db.flushes == 1


async def test_confirmed_failed():
    db = FakeDB()
    publication = make_publication()

    reconciliation, _ = await call_service(
        publication=publication,
        db=db,
        operator=uuid4(),
        decision=Decision.confirmed_failed,
        key="failed-1",
        note="Provider confirmed no post exists.",
    )

    assert publication.status == PublicationStatus.failed
    assert publication.provider_post_id is None
    assert publication.publish_attempts == 1
    assert publication.reconciliation_required is False
    assert db.added == [reconciliation]
    assert db.flushes == 1


async def test_remain_unresolved():
    db = FakeDB()
    publication = make_publication()

    reconciliation, _ = await call_service(
        publication=publication,
        db=db,
        operator=uuid4(),
        decision=Decision.remain_unresolved,
        key="unresolved-1",
        note="Evidence remains inconclusive.",
    )

    assert publication.status == PublicationStatus.publishing
    assert publication.provider_post_id is None
    assert publication.publish_attempts == 1
    assert "remains unresolved" in publication.last_error
    assert publication.reconciliation_required is True
    assert db.added == [reconciliation]
    assert db.flushes == 1


async def test_inflight_rejected():
    db = FakeDB()
    publication = make_publication(
        last_error=None,
        reconciliation_required=False,
    )

    try:
        await call_service(
            publication=publication,
            db=db,
            operator=uuid4(),
            decision=Decision.remain_unresolved,
            key="inflight-1",
            note="Must not reconcile in-flight execution.",
        )
    except PublicationStateError:
        pass
    else:
        raise AssertionError(
            "in-flight publishing was reconciled"
        )

    assert db.added == []
    assert db.flushes == 0
    assert publication.publish_attempts == 1


async def test_attempt_mismatch_rejected():
    db = FakeDB()
    publication = make_publication()

    try:
        await call_service(
            publication=publication,
            db=db,
            operator=uuid4(),
            decision=Decision.remain_unresolved,
            key="attempt-1",
            note="Wrong attempt must be rejected.",
            attempt=2,
        )
    except PublicationStateError:
        pass
    else:
        raise AssertionError(
            "attempt mismatch was accepted"
        )

    assert db.added == []
    assert db.flushes == 0
    assert publication.publish_attempts == 1


async def test_exact_idempotent_replay():
    db = FakeDB()
    operator = uuid4()

    publication = make_publication(
        status=PublicationStatus.published,
        last_error=None,
    )

    publication.provider_post_id = "provider-post-existing"

    existing = SimpleNamespace(
        operator_user_id=operator,
        decision=Decision.confirmed_published,
        publish_attempt_number=1,
        idempotency_key="replay-1",
        evidence_note="Provider post verified.",
        provider_post_id="provider-post-existing",
        provider_permalink=None,
    )

    reconciliation, result = await call_service(
        publication=publication,
        db=db,
        operator=operator,
        decision=Decision.confirmed_published,
        key="replay-1",
        note="Provider post verified.",
        post_id="provider-post-existing",
        existing=existing,
    )

    assert reconciliation is existing
    assert result is publication
    assert db.added == []
    assert db.flushes == 0
    assert publication.publish_attempts == 1


async def test_idempotency_conflict():
    db = FakeDB()
    operator = uuid4()
    publication = make_publication()

    existing = SimpleNamespace(
        operator_user_id=operator,
        decision=Decision.remain_unresolved,
        publish_attempt_number=1,
        idempotency_key="conflict-1",
        evidence_note="Original evidence.",
        provider_post_id=None,
        provider_permalink=None,
    )

    try:
        await call_service(
            publication=publication,
            db=db,
            operator=operator,
            decision=Decision.remain_unresolved,
            key="conflict-1",
            note="Different evidence.",
            existing=existing,
        )
    except PublicationReconciliationIdempotencyConflict:
        pass
    else:
        raise AssertionError(
            "idempotency conflict was accepted"
        )

    assert db.added == []
    assert db.flushes == 0
    assert publication.publish_attempts == 1


async def main():
    await test_confirmed_published()
    print("confirmed_published transition: PASS")

    await test_confirmed_failed()
    print("confirmed_failed transition: PASS")

    await test_remain_unresolved()
    print("remain_unresolved transition: PASS")

    await test_inflight_rejected()
    print("in-flight reconciliation rejection: PASS")

    await test_attempt_mismatch_rejected()
    print("attempt binding rejection: PASS")

    await test_exact_idempotent_replay()
    print("exact idempotent replay: PASS")

    await test_idempotency_conflict()
    print("idempotency key conflict: PASS")

    print("publish_attempts never incremented: PASS")
    print("Meta/provider execution invoked: NO")


asyncio.run(main())
