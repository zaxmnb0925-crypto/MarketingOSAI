import asyncio
from dataclasses import dataclass
from uuid import UUID

import app.services.publication_workflow as workflow
from app.models.publication import PublicationStatus


WORKSPACE_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)

PUBLICATION_ID = UUID(
    "22222222-2222-2222-2222-222222222222"
)

APPROVER_ID = UUID(
    "33333333-3333-3333-3333-333333333333"
)

TRIGGER_USER_ID = UUID(
    "44444444-4444-4444-4444-444444444444"
)

MESSAGE = "v0.13E audit test"


@dataclass
class FakePublication:
    status: PublicationStatus = PublicationStatus.approved
    approved_by_user_id: UUID | None = APPROVER_ID
    approved_at: object | None = object()
    content_snapshot: str = MESSAGE
    content_hash: str = workflow.content_sha256(
        MESSAGE
    )
    provider_post_id: str | None = None
    publish_attempts: int = 0
    publish_triggered_by_user_id: UUID | None = None
    publish_triggered_at: object | None = None
    last_error: str | None = "old"


class FakeDB:
    def __init__(self):
        self.flushes = 0

    async def flush(self):
        self.flushes += 1


async def main():
    original = workflow._get_publication_for_update

    publication = FakePublication()
    db = FakeDB()

    async def get_publication(
        db_arg,
        workspace_id,
        publication_id,
    ):
        assert workspace_id == WORKSPACE_ID
        assert publication_id == PUBLICATION_ID
        return publication

    workflow._get_publication_for_update = (
        get_publication
    )

    try:
        result = await workflow.begin_publication_attempt(
            db,
            WORKSPACE_ID,
            PUBLICATION_ID,
            TRIGGER_USER_ID,
        )
    finally:
        workflow._get_publication_for_update = (
            original
        )

    assert result is publication
    assert publication.status == PublicationStatus.publishing
    assert publication.publish_attempts == 1
    assert (
        publication.publish_triggered_by_user_id
        == TRIGGER_USER_ID
    )
    assert publication.publish_triggered_at is not None
    assert publication.last_error is None
    assert db.flushes == 1

    print(
        "Durable operator audit set with claim: PASS"
    )

    repeated = FakePublication(
        publish_attempts=1,
    )

    async def get_repeated(
        db_arg,
        workspace_id,
        publication_id,
    ):
        return repeated

    workflow._get_publication_for_update = (
        get_repeated
    )

    try:
        try:
            await workflow.begin_publication_attempt(
                FakeDB(),
                WORKSPACE_ID,
                PUBLICATION_ID,
                TRIGGER_USER_ID,
            )
        except workflow.PublicationStateError:
            pass
        else:
            raise AssertionError(
                "repeat publishing attempt accepted"
            )
    finally:
        workflow._get_publication_for_update = (
            original
        )

    print(
        "Repeated publishing attempt hard-blocked: PASS"
    )


asyncio.run(main())
