from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import (
    Publication,
    PublicationStatus,
    utcnow,
)
from app.models.publication_reconciliation import (
    PublicationReconciliation,
    PublicationReconciliationDecision,
)
from app.services.publication_workflow import (
    PublicationNotFound,
    PublicationStateError,
    PublicationValidationError,
    verify_snapshot_integrity,
)


class PublicationReconciliationError(RuntimeError):
    pass


class PublicationReconciliationIdempotencyConflict(
    PublicationReconciliationError
):
    pass


async def _get_publication_for_reconciliation(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
) -> Publication:
    result = await db.execute(
        select(Publication)
        .where(
            Publication.id == publication_id,
            Publication.workspace_id == workspace_id,
        )
        .with_for_update()
    )

    publication = result.scalar_one_or_none()

    if publication is None:
        raise PublicationNotFound(
            "Publication not found"
        )

    return publication


async def _get_existing_reconciliation(
    db: AsyncSession,
    publication_id: UUID,
    idempotency_key: str,
) -> PublicationReconciliation | None:
    result = await db.execute(
        select(PublicationReconciliation)
        .where(
            PublicationReconciliation.publication_id
            == publication_id,
            PublicationReconciliation.idempotency_key
            == idempotency_key,
        )
    )

    return result.scalar_one_or_none()


def _same_reconciliation_request(
    existing: PublicationReconciliation,
    *,
    operator_user_id: UUID,
    decision: PublicationReconciliationDecision,
    publish_attempt_number: int,
    evidence_note: str,
    provider_post_id: str | None,
    provider_permalink: str | None,
) -> bool:
    return (
        existing.operator_user_id == operator_user_id
        and existing.decision == decision
        and existing.publish_attempt_number
        == publish_attempt_number
        and existing.evidence_note == evidence_note
        and existing.provider_post_id
        == provider_post_id
        and existing.provider_permalink
        == provider_permalink
    )


async def reconcile_publication(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    publication_id: UUID,
    operator_user_id: UUID,
    decision: PublicationReconciliationDecision,
    publish_attempt_number: int,
    idempotency_key: str,
    evidence_note: str,
    provider_post_id: str | None = None,
    provider_permalink: str | None = None,
) -> tuple[
    PublicationReconciliation,
    Publication,
]:
    #
    # Serialize all reconciliation activity for one Publication.
    # This also protects idempotency and the terminal transition.
    #
    publication = await _get_publication_for_reconciliation(
        db,
        workspace_id,
        publication_id,
    )

    if operator_user_id is None:
        raise PublicationValidationError(
            "Reconciliation operator is required"
        )

    cleaned_key = idempotency_key.strip()

    if not cleaned_key:
        raise PublicationValidationError(
            "Reconciliation idempotency key is required"
        )

    if len(cleaned_key) > 128:
        raise PublicationValidationError(
            "Reconciliation idempotency key is too long"
        )

    cleaned_note = evidence_note.strip()

    if not cleaned_note:
        raise PublicationValidationError(
            "Reconciliation evidence note is required"
        )

    if len(cleaned_note) > 2000:
        raise PublicationValidationError(
            "Reconciliation evidence note is too long"
        )

    cleaned_post_id = (
        provider_post_id.strip()
        if provider_post_id is not None
        else None
    )

    cleaned_permalink = (
        provider_permalink.strip()
        if provider_permalink is not None
        else None
    )

    if cleaned_post_id == "":
        raise PublicationValidationError(
            "Provider post id cannot be blank"
        )

    if cleaned_permalink == "":
        raise PublicationValidationError(
            "Provider permalink cannot be blank"
        )

    #
    # Exact idempotent replay is permitted even after the first
    # request terminalized the Publication. Reusing the same key
    # for different evidence or a different decision is rejected.
    #
    existing = await _get_existing_reconciliation(
        db,
        publication_id,
        cleaned_key,
    )

    if existing is not None:
        if not _same_reconciliation_request(
            existing,
            operator_user_id=operator_user_id,
            decision=decision,
            publish_attempt_number=publish_attempt_number,
            evidence_note=cleaned_note,
            provider_post_id=cleaned_post_id,
            provider_permalink=cleaned_permalink,
        ):
            raise PublicationReconciliationIdempotencyConflict(
                "Reconciliation idempotency key already exists "
                "with different request data"
            )

        return existing, publication

    #
    # New reconciliation decisions are valid only for an
    # ambiguous provider outcome.
    #
    if (
        publication.status
        != PublicationStatus.publishing
    ):
        raise PublicationStateError(
            "Only publishing publications "
            "can be reconciled"
        )

    verify_snapshot_integrity(publication)

    if publication.provider_post_id is not None:
        raise PublicationStateError(
            "Publication already has a provider post id"
        )

    if (
        publication.publish_triggered_by_user_id is None
        or publication.publish_triggered_at is None
    ):
        raise PublicationStateError(
            "Publication publish trigger audit is incomplete"
        )

    if publication.publish_attempts < 1:
        raise PublicationStateError(
            "Publication has no publishing attempt"
        )

    if (
        publication.publish_attempts
        != publish_attempt_number
    ):
        raise PublicationStateError(
            "Reconciliation attempt does not match "
            "the current publishing attempt"
        )

    #
    # Reconciliation is allowed only after the executor has
    # durably persisted an ambiguous provider outcome.
    #
    if not publication.reconciliation_required:
        raise PublicationStateError(
            "Publication does not require reconciliation"
        )

    if (
        decision
        == PublicationReconciliationDecision.confirmed_published
    ):
        if cleaned_post_id is None:
            raise PublicationValidationError(
                "confirmed_published requires provider_post_id"
            )

    else:
        if (
            cleaned_post_id is not None
            or cleaned_permalink is not None
        ):
            raise PublicationValidationError(
                "Provider post fields are only valid "
                "for confirmed_published"
            )

    reconciliation = PublicationReconciliation(
        publication_id=publication.id,
        workspace_id=publication.workspace_id,
        operator_user_id=operator_user_id,
        decision=decision,
        publish_attempt_number=publish_attempt_number,
        idempotency_key=cleaned_key,
        provider_post_id=cleaned_post_id,
        provider_permalink=cleaned_permalink,
        evidence_note=cleaned_note,
    )

    db.add(reconciliation)

    if (
        decision
        == PublicationReconciliationDecision.confirmed_published
    ):
        publication.provider_post_id = cleaned_post_id
        publication.provider_permalink = cleaned_permalink
        publication.published_at = utcnow()
        publication.status = PublicationStatus.published
        publication.last_error = None
        publication.reconciliation_required = False

    elif (
        decision
        == PublicationReconciliationDecision.confirmed_failed
    ):
        publication.status = PublicationStatus.failed
        publication.last_error = (
            "Publishing outcome reconciled as failed"
        )
        publication.reconciliation_required = False

    elif (
        decision
        == PublicationReconciliationDecision.remain_unresolved
    ):
        #
        # Do not alter publish_attempts and never make this row
        # retryable. The provider may already have performed the
        # external side effect.
        #
        publication.status = PublicationStatus.publishing
        publication.last_error = (
            "Publishing outcome remains unresolved; "
            "manual reconciliation required"
        )
        publication.reconciliation_required = True

    else:
        raise PublicationValidationError(
            "Unsupported reconciliation decision"
        )

    #
    # Audit row and Publication transition are flushed together.
    # The caller owns commit/rollback.
    #
    await db.flush()

    return reconciliation, publication
