from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import (
    Publication,
    PublicationStatus,
)
from app.models.social_account import (
    SocialAccount,
    SocialAccountStatus,
    SocialPlatform,
)
from app.services.meta_publishing import (
    MetaPublishDryRun,
    dry_run_meta_page_text_publish,
)
from app.services.publication_workflow import (
    PublicationNotFound,
    PublicationStateError,
    PublicationValidationError,
    verify_snapshot_integrity,
)


async def build_publication_meta_dry_run(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
) -> MetaPublishDryRun:
    result = await db.execute(
        select(Publication).where(
            Publication.id == publication_id,
            Publication.workspace_id
            == workspace_id,
        )
    )

    publication = (
        result.scalar_one_or_none()
    )

    if publication is None:
        raise PublicationNotFound(
            "Publication not found"
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

    if publication.social_account_id is None:
        raise PublicationValidationError(
            "Publication social account "
            "is missing"
        )

    account_result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id
            == publication.social_account_id,
            SocialAccount.workspace_id
            == workspace_id,
        )
    )

    account = (
        account_result.scalar_one_or_none()
    )

    if account is None:
        raise PublicationValidationError(
            "Publication social account "
            "was not found"
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

    if (
        account.platform
        != SocialPlatform.facebook
    ):
        raise PublicationValidationError(
            "Publication target is not "
            "a Facebook account"
        )

    if publication.platform != "facebook":
        raise PublicationValidationError(
            "Publication platform is not Facebook"
        )

    if not account.platform_account_id:
        raise PublicationValidationError(
            "Social account target id is missing"
        )

    #
    # The live SocialAccount must still represent
    # the exact provider asset approved in the
    # Publication snapshot.
    #
    if (
        account.platform_account_id
        != publication.target_account_id
    ):
        raise PublicationStateError(
            "Publication target account "
            "no longer matches"
        )

    if (
        account.brand_id is not None
        and publication.brand_id is not None
        and account.brand_id
        != publication.brand_id
    ):
        raise PublicationStateError(
            "Publication brand target "
            "no longer matches"
        )

    #
    # Presence check only.
    # Dry-run must never decrypt or expose this field.
    #
    if not account.access_token_ciphertext:
        raise PublicationValidationError(
            "Social account credential is missing"
        )

    dry_run = dry_run_meta_page_text_publish(
        publication.target_account_id,
        publication.content_snapshot,
    )

    #
    # Defense in depth:
    # ensure adapter metadata was generated from
    # exactly the approved Publication snapshot.
    #
    if dry_run.content_hash != publication.content_hash:
        raise PublicationStateError(
            "Publication dry-run content "
            "integrity check failed"
        )

    return dry_run
