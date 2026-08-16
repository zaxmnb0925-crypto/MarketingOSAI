from .common import (
    AsyncSession,
    ContentGeneration,
    ContentStatus,
    Publication,
    PublicationIdempotencyConflict,
    PublicationStateError,
    PublicationStatus,
    PublicationValidationError,
    SocialAccount,
    SocialAccountStatus,
    UUID,
    select,
    utcnow,
)

from .integrity import (
    content_sha256,
    verify_snapshot_integrity,
)

from .locking import (
    _get_publication_for_update,
)

async def create_publication_draft(
    db: AsyncSession,
    workspace_id: UUID,
    content_generation_id: UUID,
    social_account_id: UUID,
    created_by_user_id: UUID,
    idempotency_key: str,
) -> Publication:
    if not idempotency_key:
        raise PublicationValidationError(
            "Idempotency key is required"
        )

    if len(idempotency_key) > 128:
        raise PublicationValidationError(
            "Idempotency key is too long"
        )

    #
    # Application-level idempotency check.
    # The PostgreSQL UNIQUE constraint remains the
    # final concurrency-safe enforcement layer.
    #
    existing_result = await db.execute(
        select(Publication).where(
            Publication.workspace_id
            == workspace_id,
            Publication.idempotency_key
            == idempotency_key,
        )
    )

    existing = (
        existing_result.scalar_one_or_none()
    )

    if existing is not None:
        same_request = (
            existing.content_generation_id
            == content_generation_id
            and existing.social_account_id
            == social_account_id
            and existing.created_by_user_id
            == created_by_user_id
        )

        if not same_request:
            raise PublicationIdempotencyConflict(
                "Idempotency key was already used "
                "for a different publication request"
            )

        return existing

    generation_result = await db.execute(
        select(ContentGeneration).where(
            ContentGeneration.id
            == content_generation_id,
            ContentGeneration.workspace_id
            == workspace_id,
        )
    )

    generation = (
        generation_result.scalar_one_or_none()
    )

    if generation is None:
        raise PublicationValidationError(
            "Content generation not found"
        )

    if generation.status != ContentStatus.completed:
        raise PublicationValidationError(
            "Only completed content can "
            "create a publication draft"
        )

    if (
        not generation.generated_content
        or not generation.generated_content.strip()
    ):
        raise PublicationValidationError(
            "Completed content has no "
            "generated content"
        )

    account_result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id
            == social_account_id,
            SocialAccount.workspace_id
            == workspace_id,
        )
    )

    account = (
        account_result.scalar_one_or_none()
    )

    if account is None:
        raise PublicationValidationError(
            "Social account not found"
        )

    if (
        account.status
        != SocialAccountStatus.connected
    ):
        raise PublicationValidationError(
            "Social account is not connected"
        )

    if not account.is_active:
        raise PublicationValidationError(
            "Social account is inactive"
        )

    if not account.platform_account_id:
        raise PublicationValidationError(
            "Social account target id is missing"
        )

    if not account.access_token_ciphertext:
        raise PublicationValidationError(
            "Social account credential is missing"
        )

    if (
        generation.platform.value
        != account.platform.value
    ):
        raise PublicationValidationError(
            "Content platform does not match "
            "the social account platform"
        )

    if (
        account.brand_id is not None
        and account.brand_id
        != generation.brand_id
    ):
        raise PublicationValidationError(
            "Social account belongs to "
            "a different brand"
        )

    #
    # Preserve the exact generated content.
    # Do not trim, normalize, or read live content
    # again after this snapshot is created.
    #
    snapshot = generation.generated_content

    publication = Publication(
        workspace_id=workspace_id,
        brand_id=generation.brand_id,
        content_generation_id=generation.id,
        social_account_id=account.id,
        created_by_user_id=created_by_user_id,
        status=PublicationStatus.draft,
        platform=account.platform.value,
        target_account_id=(
            account.platform_account_id
        ),
        target_account_name=(
            account.account_name
        ),
        content_snapshot=snapshot,
        content_hash=content_sha256(
            snapshot
        ),
        idempotency_key=idempotency_key,
        publish_attempts=0,
    )

    db.add(publication)

    # Caller owns commit/rollback.
    await db.flush()

    return publication


async def approve_publication(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    approved_by_user_id: UUID,
) -> Publication:
    publication = (
        await _get_publication_for_update(
            db,
            workspace_id,
            publication_id,
        )
    )

    #
    # Approval is idempotent after it has already
    # succeeded. Never overwrite the original
    # approver/audit timestamp.
    #
    if (
        publication.status
        == PublicationStatus.approved
    ):
        verify_snapshot_integrity(
            publication
        )

        if (
            publication.approved_by_user_id
            is None
            or publication.approved_at is None
        ):
            raise PublicationStateError(
                "Approved publication is missing "
                "approval audit fields"
            )

        return publication

    if (
        publication.status
        != PublicationStatus.draft
    ):
        raise PublicationStateError(
            "Only draft publications "
            "can be approved"
        )

    verify_snapshot_integrity(
        publication
    )

    publication.approved_by_user_id = (
        approved_by_user_id
    )
    publication.approved_at = utcnow()
    publication.status = (
        PublicationStatus.approved
    )
    publication.last_error = None

    await db.flush()

    return publication
