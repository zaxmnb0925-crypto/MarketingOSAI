from uuid import UUID

from app.core.config import settings


class PublicationCanaryTargetRejected(
    RuntimeError
):
    """
    The exact server-side first-live-post canary target is
    either not configured or does not match this request.

    Deliberately use one generic exception for both cases so
    callers do not expose the configured target.
    """

    pass


def require_exact_publication_canary_target(
    *,
    workspace_id: UUID,
    publication_id: UUID,
) -> None:
    """
    Require the request to match the one exact Publication
    selected server-side for the first-live-post canary.

    Safety properties:

    - default unset => fail closed
    - partial configuration => fail closed
    - wrong Workspace => fail closed
    - wrong Publication => fail closed
    - exact Workspace + Publication => allowed

    These identifiers are not secrets. They are server-side
    control-plane configuration and must never be inferred
    from the activation bearer.
    """

    configured_workspace_id = (
        settings.meta_publish_canary_workspace_id
    )

    configured_publication_id = (
        settings.meta_publish_canary_publication_id
    )

    if (
        configured_workspace_id is None
        or configured_publication_id is None
    ):
        raise PublicationCanaryTargetRejected(
            "Publication canary target unavailable"
        )

    if (
        workspace_id
        != configured_workspace_id
        or publication_id
        != configured_publication_id
    ):
        raise PublicationCanaryTargetRejected(
            "Publication canary target unavailable"
        )
