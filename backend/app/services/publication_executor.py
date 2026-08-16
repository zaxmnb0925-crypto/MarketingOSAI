import logging
from dataclasses import dataclass, field
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
    MetaPublishResult,
    MetaPublishingOutcomeUnknown,
    MetaPublishingProviderError,
    MetaPublishingTransport,
    MetaPublishingValidationError,
    publish_meta_page_text_with_transport,
)
from app.services.oauth_crypto import (
    oauth_token_cipher,
)
from app.services.publication_workflow import (
    PublicationNotFound,
    PublicationStateError,
    PublicationValidationError,
    begin_publication_attempt,
    mark_publication_execution_unknown,
    mark_publication_failed,
    mark_publication_published,
    verify_snapshot_integrity,
)


class PublicationExecutionError(RuntimeError):
    pass


class PublicationExecutionProviderRejected(
    PublicationExecutionError
):
    pass


class PublicationExecutionOutcomeUnknown(
    PublicationExecutionError
):
    pass


@dataclass(frozen=True)
class PublicationExecutionContext:
    page_id: str

    # Exact approved Publication snapshot.
    message: str = field(repr=False)

    content_hash: str

    # Ciphertext is never included in dataclass repr.
    access_token_ciphertext: str = field(
        repr=False
    )


async def _load_execution_context(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
) -> PublicationExecutionContext:
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

    #
    # The durable claim must already have committed before
    # credential decryption or provider execution.
    #
    if (
        publication.status
        != PublicationStatus.publishing
    ):
        raise PublicationStateError(
            "Publication is not in publishing state"
        )

    if (
        publication.approved_by_user_id is None
        or publication.approved_at is None
    ):
        raise PublicationStateError(
            "Publication approval audit is incomplete"
        )

    verify_snapshot_integrity(
        publication
    )

    if publication.provider_post_id is not None:
        raise PublicationStateError(
            "Publication already has a provider post id"
        )

    if publication.platform != "facebook":
        raise PublicationValidationError(
            "Publication platform is not Facebook"
        )

    if not publication.target_account_id:
        raise PublicationValidationError(
            "Publication target account is missing"
        )

    if publication.social_account_id is None:
        raise PublicationValidationError(
            "Publication social account is missing"
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
            "Publication social account was not found"
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
            "Publication target is not a Facebook account"
        )

    if not account.platform_account_id:
        raise PublicationValidationError(
            "Social account target id is missing"
        )

    if (
        account.platform_account_id
        != publication.target_account_id
    ):
        raise PublicationStateError(
            "Publication target account no longer matches"
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

    if not account.access_token_ciphertext:
        raise PublicationValidationError(
            "Social account credential is missing"
        )

    return PublicationExecutionContext(
        page_id=publication.target_account_id,
        message=publication.content_snapshot,
        content_hash=publication.content_hash,
        access_token_ciphertext=(
            account.access_token_ciphertext
        ),
    )


async def _persist_definite_failure(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    safe_error: str,
) -> None:
    try:
        await mark_publication_failed(
            db,
            workspace_id,
            publication_id,
            safe_error,
        )
        await db.commit()
    except Exception:
        await db.rollback()

        #
        # The durable claim remains `publishing` because
        # it was committed before provider execution.
        #
        raise PublicationExecutionError(
            "Publication failure state "
            "could not be persisted"
        ) from None


async def _persist_unknown_outcome(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
) -> None:
    try:
        await mark_publication_execution_unknown(
            db,
            workspace_id,
            publication_id,
        )
        await db.commit()
    except Exception:
        logging.warning("Suppressed exception in publication_executor.py._persist_unknown_outcome; continuing according to existing control flow", exc_info=True)
        await db.rollback()

        #
        # Even if this best-effort annotation fails,
        # the previously committed `publishing` claim
        # prevents an automatic second provider request.
        #
        pass


async def execute_meta_publication_with_transport(
    *,
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    triggered_by_user_id: UUID,
    transport: MetaPublishingTransport,
) -> MetaPublishResult:
    """
    Execute one already-approved Facebook Publication.

    This service intentionally requires an injected
    transport. It never constructs the real HTTP transport
    by itself.

    Safety sequence:

      approved
         |
         | durable DB claim + COMMIT
         v
      publishing
         |
         | revalidate target + decrypt credential
         | as late as possible
         v
      provider request
         |
         +--> definite rejection -> failed
         |
         +--> ambiguous outcome -> remain publishing
         |
         +--> confirmed post id -> published

    No automatic retry exists here.
    """

    #
    # PHASE 1 — durable execution claim.
    #
    # This commit MUST happen before any credential
    # decryption or provider request.
    #
    try:
        await begin_publication_attempt(
            db,
            workspace_id,
            publication_id,
            triggered_by_user_id,
        )

        await db.commit()

    except Exception:
        await db.rollback()
        raise

    #
    # PHASE 2 — re-read and revalidate live state after
    # the durable claim has committed.
    #
    try:
        context = await _load_execution_context(
            db,
            workspace_id,
            publication_id,
        )

    except (
        PublicationNotFound,
        PublicationStateError,
        PublicationValidationError,
    ):
        await _persist_definite_failure(
            db,
            workspace_id,
            publication_id,
            "Publication execution validation failed",
        )

        raise PublicationExecutionError(
            "Publication execution validation failed"
        ) from None

    #
    # PHASE 3 — narrow credential decryption boundary.
    #
    # Plaintext exists only immediately around the provider
    # call and is never persisted or returned.
    #
    try:
        page_token = oauth_token_cipher.decrypt(
            context.access_token_ciphertext
        )

    except Exception:
        await _persist_definite_failure(
            db,
            workspace_id,
            publication_id,
            "Social account credential "
            "could not be decrypted",
        )

        raise PublicationExecutionError(
            "Social account credential "
            "could not be decrypted"
        ) from None

    try:
        result = (
            await publish_meta_page_text_with_transport(
                page_id=context.page_id,
                page_access_token=page_token,
                message=context.message,
                transport=transport,
            )
        )

    except MetaPublishingOutcomeUnknown:
        #
        # Request may have reached Meta.
        # Do not mark this as a normal retryable failure.
        #
        await _persist_unknown_outcome(
            db,
            workspace_id,
            publication_id,
        )

        raise PublicationExecutionOutcomeUnknown(
            "Meta publishing outcome is unknown; "
            "manual reconciliation required"
        ) from None

    except MetaPublishingProviderError as exc:
        #
        # Concrete Meta transport uses this class for
        # definite provider rejection / invalid response
        # cases that are not classified outcome-unknown.
        #
        await _persist_definite_failure(
            db,
            workspace_id,
            publication_id,
            str(exc),
        )

        raise PublicationExecutionProviderRejected(
            str(exc)
        ) from None

    except MetaPublishingValidationError:
        await _persist_definite_failure(
            db,
            workspace_id,
            publication_id,
            "Meta publishing validation failed",
        )

        raise PublicationExecutionError(
            "Meta publishing validation failed"
        ) from None

    finally:
        #
        # Best-effort reduction of plaintext lifetime.
        #
        page_token = None

    #
    # PHASE 4 — confirmed provider result.
    #
    # If local finalization fails after Meta returned a
    # post id, the provider side has already succeeded.
    # Therefore this is also outcome-unknown from the
    # application's durable-state perspective and must
    # never trigger automatic retry.
    #
    try:
        await mark_publication_published(
            db,
            workspace_id,
            publication_id,
            result.provider_post_id,
            result.provider_permalink,
        )

        await db.commit()

    except Exception:
        await db.rollback()

        await _persist_unknown_outcome(
            db,
            workspace_id,
            publication_id,
        )

        raise PublicationExecutionOutcomeUnknown(
            "Meta post may have been created; "
            "local finalization requires reconciliation"
        ) from None

    return result
