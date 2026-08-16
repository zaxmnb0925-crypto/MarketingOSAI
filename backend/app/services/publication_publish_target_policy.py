from uuid import UUID

from app.core.config import settings
from app.services.publication_canary_target import (
    PublicationCanaryTargetRejected,
    require_exact_publication_canary_target,
)


class PublicationPublishTargetRejected(
    RuntimeError
):
    pass


def require_allowed_publication_publish_target(
    *,
    workspace_id: UUID,
    publication_id: UUID,
) -> None:
    """
    Enforce the server-side publishing target policy.

    Canary mode (default / fail-closed):
        Only the exact configured Workspace + Publication
        may pass.

    Normal mode:
        The exact canary target restriction is disabled.
        Authorization, approval, immutable content hash,
        connected target-account validation, one-time grants,
        kill switches, durable execution claim and provider
        outcome handling remain separate mandatory gates.

    This helper performs no database access, Redis access,
    credential decryption or network request.
    """

    if not settings.meta_publish_canary_mode_enabled:
        return

    try:
        require_exact_publication_canary_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )
    except PublicationCanaryTargetRejected:
        raise PublicationPublishTargetRejected(
            "Publication publishing target unavailable"
        ) from None
