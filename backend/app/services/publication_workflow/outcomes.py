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

async def mark_publication_published(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    provider_post_id: str,
    provider_permalink: str | None = None,
) -> Publication:
    publication = (
        await _get_publication_for_update(
            db,
            workspace_id,
            publication_id,
        )
    )

    if (
        publication.status
        != PublicationStatus.publishing
    ):
        raise PublicationStateError(
            "Only publishing publications "
            "can be marked published"
        )

    verify_snapshot_integrity(
        publication
    )

    if not provider_post_id:
        raise PublicationValidationError(
            "Provider post id is required"
        )

    publication.provider_post_id = (
        provider_post_id
    )
    publication.provider_permalink = (
        provider_permalink
    )
    publication.published_at = utcnow()
    publication.status = (
        PublicationStatus.published
    )
    publication.last_error = None
    publication.reconciliation_required = False

    await db.flush()

    return publication


async def mark_publication_failed(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    safe_error: str,
) -> Publication:
    publication = (
        await _get_publication_for_update(
            db,
            workspace_id,
            publication_id,
        )
    )

    if (
        publication.status
        != PublicationStatus.publishing
    ):
        raise PublicationStateError(
            "Only publishing publications "
            "can be marked failed"
        )

    if not safe_error:
        safe_error = "Publishing failed"

    #
    # This field is intended for sanitized operational
    # errors only. Raw provider bodies, OAuth tokens,
    # ciphertext, and request headers must never be
    # passed by the provider adapter.
    #
    publication.last_error = (
        safe_error[:500]
    )
    publication.status = (
        PublicationStatus.failed
    )
    publication.reconciliation_required = False

    await db.flush()

    return publication


async def mark_publication_execution_unknown(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    safe_error: str = (
        "Publishing outcome is unknown; "
        "manual reconciliation required"
    ),
) -> Publication:
    """
    Record an ambiguous provider outcome without making
    the Publication retryable.

    The Publication intentionally remains in `publishing`.
    An operator must reconcile provider state before any
    future retry is considered.
    """
    publication = (
        await _get_publication_for_update(
            db,
            workspace_id,
            publication_id,
        )
    )

    if (
        publication.status
        != PublicationStatus.publishing
    ):
        raise PublicationStateError(
            "Only publishing publications "
            "can enter reconciliation"
        )

    verify_snapshot_integrity(
        publication
    )

    if publication.provider_post_id is not None:
        raise PublicationStateError(
            "Publication already has a provider post id"
        )

    if not safe_error:
        safe_error = (
            "Publishing outcome is unknown; "
            "manual reconciliation required"
        )

    #
    # Deliberately remain PublicationStatus.publishing.
    # This prevents begin_publication_attempt() from
    # automatically sending the Publication again.
    #
    publication.last_error = safe_error[:500]
    publication.reconciliation_required = True

    await db.flush()

    return publication
