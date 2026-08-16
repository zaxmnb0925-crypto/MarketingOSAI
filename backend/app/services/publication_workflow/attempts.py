from .common import (
    AsyncSession,
    Publication,
    PublicationStateError,
    PublicationStatus,
    PublicationValidationError,
    UUID,
    utcnow,
)

from .integrity import (
    verify_snapshot_integrity,
)

from .locking import (
    _get_publication_for_update,
)

async def begin_publication_attempt(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    triggered_by_user_id: UUID,
) -> Publication:
    #
    # SELECT ... FOR UPDATE prevents two workers
    # from simultaneously transitioning the same
    # approved publication into publishing.
    #
    publication = (
        await _get_publication_for_update(
            db,
            workspace_id,
            publication_id,
        )
    )

    if (
        publication.status
        != PublicationStatus.approved
    ):
        raise PublicationStateError(
            "Publication is not approved"
        )

    if (
        publication.approved_by_user_id
        is None
        or publication.approved_at is None
    ):
        raise PublicationStateError(
            "Publication approval audit "
            "is incomplete"
        )

    verify_snapshot_integrity(
        publication
    )

    if publication.provider_post_id is not None:
        raise PublicationStateError(
            "Publication already has "
            "a provider post id"
        )

    if triggered_by_user_id is None:
        raise PublicationValidationError(
            "Publishing operator is required"
        )

    #
    # v0.13E intentionally permits only the first provider
    # execution attempt. Future explicit retry/reconciliation
    # design must not silently bypass this gate.
    #
    if publication.publish_attempts != 0:
        raise PublicationStateError(
            "Publication already has a publishing attempt"
        )

    if (
        publication.publish_triggered_by_user_id
        is not None
        or publication.publish_triggered_at is not None
    ):
        raise PublicationStateError(
            "Publication publish trigger audit "
            "already exists"
        )

    #
    # These audit fields are written inside the same
    # SELECT FOR UPDATE transaction as the durable
    # approved -> publishing claim.
    #
    publication.publish_triggered_by_user_id = (
        triggered_by_user_id
    )
    publication.publish_triggered_at = utcnow()

    publication.status = (
        PublicationStatus.publishing
    )

    publication.publish_attempts += 1
    publication.last_error = None
    publication.reconciliation_required = False

    await db.flush()

    return publication
