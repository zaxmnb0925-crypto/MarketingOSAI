from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.publication_activation import (
    PublicationActivationError,
    consume_and_verify_publication_activation,
)
from app.services.publication_controlled_execution import (
    ControlledPublicationContentHashMismatch,
    ControlledPublicationExecutionDisabled,
)
from app.services.publication_dry_run import (
    build_publication_meta_dry_run,
)


class ControlledPublicationActivationRejected(
    RuntimeError
):
    pass


async def verify_and_consume_publication_activation_for_execution(
    *,
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    user_id: UUID,
    activation_value: str,
    expected_content_hash: str,
) -> None:
    """
    Consume the publication-specific activation grant before
    the existing publication confirmation is consumed.

    Safety sequence:

        real publishing switch
                |
                v
        Meta transport wiring switch
                |
                v
        approved/read-only dry-run
                |
                v
        exact current content hash
                |
                v
        atomic activation GETDEL

    The caller must invoke the existing controlled execution
    layer only after this function succeeds.

    This service performs no credential decryption and no
    provider network request.
    """

    #
    # Defense in depth. The HTTP endpoint has already checked
    # the real publishing switch and requested the provider
    # factory, but the activation bearer must not be consumed
    # unless both global controls are still enabled.
    #
    if not settings.real_publish_enabled:
        raise ControlledPublicationExecutionDisabled(
            "Real publishing is disabled"
        )

    if not settings.meta_publish_transport_enabled:
        raise ControlledPublicationExecutionDisabled(
            "Real publishing transport is disabled"
        )

    #
    # Defense in depth: exact server-side canary target must
    # match before dry-run, activation GETDEL, durable claim,
    # credential decryption, or provider execution.
    #
    from app.services.publication_publish_target_policy import (
        PublicationPublishTargetRejected,
        require_allowed_publication_publish_target,
    )

    try:
        require_allowed_publication_publish_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )
    except PublicationPublishTargetRejected:
        raise ControlledPublicationActivationRejected(
            "Publication activation is invalid "
            "or no longer available"
        ) from None

    #
    # Re-read the exact approved Publication immediately before
    # consuming the one-time activation bearer.
    #
    dry_run = await build_publication_meta_dry_run(
        db,
        workspace_id,
        publication_id,
    )

    if (
        not isinstance(
            expected_content_hash,
            str,
        )
        or expected_content_hash
        != dry_run.content_hash
    ):
        raise ControlledPublicationContentHashMismatch(
            "Publication content hash no longer matches"
        )

    try:
        await consume_and_verify_publication_activation(
            activation_value=activation_value,
            expected_workspace_id=workspace_id,
            expected_publication_id=publication_id,
            expected_user_id=user_id,
            expected_content_hash=(
                dry_run.content_hash
            ),
        )
    except PublicationActivationError:
        raise ControlledPublicationActivationRejected(
            "Publication activation is invalid "
            "or no longer available"
        ) from None
