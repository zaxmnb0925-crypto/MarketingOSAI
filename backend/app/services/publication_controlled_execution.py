from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.meta_publishing import (
    MetaPublishResult,
    MetaPublishingTransport,
)
from app.services.publication_confirmation import (
    PublicationConfirmationError,
    consume_and_verify_publication_confirmation,
)
from app.services.publication_dry_run import (
    build_publication_meta_dry_run,
)
from app.services.publication_executor import (
    execute_meta_publication_with_transport,
)


class ControlledPublicationExecutionError(
    RuntimeError
):
    pass


class ControlledPublicationExecutionDisabled(
    ControlledPublicationExecutionError
):
    pass


class ControlledPublicationContentHashMismatch(
    ControlledPublicationExecutionError
):
    pass


class ControlledPublicationConfirmationRejected(
    ControlledPublicationExecutionError
):
    pass


async def execute_confirmed_meta_publication_with_transport(
    *,
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
    user_id: UUID,
    confirmation_value: str,
    expected_content_hash: str,
    transport: MetaPublishingTransport,
) -> MetaPublishResult:
    """
    Controlled orchestration boundary for one confirmed
    Facebook Publication.

    This service deliberately accepts an injected provider
    transport. It never constructs MetaGraphHTTPTransport.

    Safety sequence:

      kill switch
          |
          v
      approved/read-only preflight
          |
          v
      exact current content-hash check
          |
          v
      atomic one-time confirmation consume
          |
          v
      durable execution claim inside executor
          |
          v
      injected transport only

    No automatic retry is introduced here.
    """

    #
    # Fail closed before touching Redis or Publication state.
    #
    if not settings.real_publish_enabled:
        raise ControlledPublicationExecutionDisabled(
            "Real publishing is disabled"
        )

    #
    # Revalidate the current approved snapshot and target
    # immediately before consuming the one-time confirmation.
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

    #
    # GETDEL occurs inside the confirmation service.
    # Once we cross this boundary, the confirmation cannot
    # be replayed even if later execution fails.
    #
    try:
        await consume_and_verify_publication_confirmation(
            confirmation_value=confirmation_value,
            expected_workspace_id=workspace_id,
            expected_publication_id=publication_id,
            expected_user_id=user_id,
            expected_content_hash=(
                dry_run.content_hash
            ),
        )
    except PublicationConfirmationError:
        raise ControlledPublicationConfirmationRejected(
            "Publication confirmation is invalid "
            "or no longer available"
        ) from None

    #
    # The executor owns:
    # - durable approved -> publishing claim
    # - operator audit
    # - attempts increment
    # - late credential decryption
    # - provider outcome classification
    #
    # Its transport remains injected.
    #
    return await execute_meta_publication_with_transport(
        db=db,
        workspace_id=workspace_id,
        publication_id=publication_id,
        triggered_by_user_id=user_id,
        transport=transport,
    )
