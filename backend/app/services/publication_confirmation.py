import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from app.services.publication_confirmation_store import (
    consume_publication_confirmation,
    register_publication_confirmation,
)


PUBLICATION_CONFIRMATION_TTL_SECONDS = 180


class PublicationConfirmationError(RuntimeError):
    pass


class PublicationConfirmationInvalid(
    PublicationConfirmationError
):
    pass


class PublicationConfirmationExpired(
    PublicationConfirmationError
):
    pass


class PublicationConfirmationReplay(
    PublicationConfirmationError
):
    pass


@dataclass(frozen=True)
class PublicationConfirmationPayload:
    workspace_id: UUID
    publication_id: UUID
    user_id: UUID
    content_hash: str
    issued_at: int


def _validate_content_hash(
    content_hash: str,
) -> None:
    if (
        not isinstance(content_hash, str)
        or len(content_hash) != 64
        or any(
            char not in "0123456789abcdef"
            for char in content_hash
        )
    ):
        raise PublicationConfirmationInvalid(
            "Publication content hash is invalid"
        )


async def create_publication_confirmation(
    *,
    workspace_id: UUID,
    publication_id: UUID,
    user_id: UUID,
    content_hash: str,
) -> str:
    _validate_content_hash(
        content_hash
    )

    issued_at = int(
        time.time()
    )

    #
    # Opaque 256-bit random confirmation value.
    # IDs and hashes are stored server-side in Redis,
    # never embedded into the value returned to callers.
    #
    confirmation_value = (
        secrets.token_urlsafe(32)
    )

    payload = {
        "workspace_id": str(workspace_id),
        "publication_id": str(publication_id),
        "user_id": str(user_id),
        "content_hash": content_hash,
        "issued_at": issued_at,
    }

    await register_publication_confirmation(
        confirmation_value,
        payload,
        ttl_seconds=(
            PUBLICATION_CONFIRMATION_TTL_SECONDS
        ),
    )

    return confirmation_value


async def consume_and_verify_publication_confirmation(
    *,
    confirmation_value: str,
    expected_workspace_id: UUID,
    expected_publication_id: UUID,
    expected_user_id: UUID,
    expected_content_hash: str,
) -> PublicationConfirmationPayload:
    if not confirmation_value:
        raise PublicationConfirmationInvalid(
            "Publication confirmation is missing"
        )

    _validate_content_hash(
        expected_content_hash
    )

    #
    # Atomic GETDEL occurs before validation.
    # A stolen/misbound value therefore fails closed
    # and cannot later be replayed with different IDs.
    #
    data = await consume_publication_confirmation(
        confirmation_value
    )

    if data is None:
        raise PublicationConfirmationReplay(
            "Publication confirmation "
            "already used or expired"
        )

    try:
        workspace_id = UUID(
            str(data["workspace_id"])
        )
        publication_id = UUID(
            str(data["publication_id"])
        )
        user_id = UUID(
            str(data["user_id"])
        )
        content_hash = str(
            data["content_hash"]
        )
        issued_at = int(
            data["issued_at"]
        )
    except Exception as exc:
        raise PublicationConfirmationInvalid(
            "Publication confirmation payload "
            "is invalid"
        ) from exc

    _validate_content_hash(
        content_hash
    )

    now = int(
        time.time()
    )

    if issued_at > now + 30:
        raise PublicationConfirmationInvalid(
            "Publication confirmation "
            "issued_at is invalid"
        )

    if (
        now - issued_at
        > PUBLICATION_CONFIRMATION_TTL_SECONDS
    ):
        raise PublicationConfirmationExpired(
            "Publication confirmation expired"
        )

    if (
        workspace_id
        != expected_workspace_id
        or publication_id
        != expected_publication_id
        or user_id
        != expected_user_id
        or content_hash
        != expected_content_hash
    ):
        raise PublicationConfirmationInvalid(
            "Publication confirmation "
            "binding mismatch"
        )

    return PublicationConfirmationPayload(
        workspace_id=workspace_id,
        publication_id=publication_id,
        user_id=user_id,
        content_hash=content_hash,
        issued_at=issued_at,
    )
