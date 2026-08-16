import secrets
import time
from dataclasses import dataclass
from uuid import UUID

from app.services.publication_activation_store import (
    consume_publication_activation,
    register_publication_activation,
)


#
# Deliberately shorter than the existing publication
# confirmation TTL.
#
PUBLICATION_ACTIVATION_TTL_SECONDS = 120


class PublicationActivationError(
    RuntimeError
):
    pass


class PublicationActivationInvalid(
    PublicationActivationError
):
    pass


class PublicationActivationExpired(
    PublicationActivationError
):
    pass


class PublicationActivationReplay(
    PublicationActivationError
):
    pass


@dataclass(frozen=True)
class PublicationActivationPayload:
    workspace_id: UUID
    publication_id: UUID
    user_id: UUID
    content_hash: str
    issued_at: int


def _validate_content_hash(
    content_hash: str,
) -> None:
    if (
        not isinstance(
            content_hash,
            str,
        )
        or len(
            content_hash
        ) != 64
        or any(
            char not in "0123456789abcdef"
            for char in content_hash
        )
    ):
        raise PublicationActivationInvalid(
            "Publication content hash is invalid"
        )


async def create_publication_activation(
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
    # Opaque 256-bit bearer. Binding information remains
    # server-side only.
    #
    activation_value = (
        secrets.token_urlsafe(
            32
        )
    )

    payload = {
        "workspace_id": str(
            workspace_id
        ),
        "publication_id": str(
            publication_id
        ),
        "user_id": str(
            user_id
        ),
        "content_hash": content_hash,
        "issued_at": issued_at,
    }

    await register_publication_activation(
        activation_value,
        payload,
        ttl_seconds=(
            PUBLICATION_ACTIVATION_TTL_SECONDS
        ),
    )

    return activation_value


async def consume_and_verify_publication_activation(
    *,
    activation_value: str,
    expected_workspace_id: UUID,
    expected_publication_id: UUID,
    expected_user_id: UUID,
    expected_content_hash: str,
) -> PublicationActivationPayload:
    if not activation_value:
        raise PublicationActivationInvalid(
            "Publication activation is missing"
        )

    _validate_content_hash(
        expected_content_hash
    )

    #
    # Atomic GETDEL occurs before validating the binding.
    # A stolen or misbound bearer therefore fails closed
    # and cannot be retried against another target.
    #
    data = await consume_publication_activation(
        activation_value
    )

    if data is None:
        raise PublicationActivationReplay(
            "Publication activation already used or expired"
        )

    try:
        workspace_id = UUID(
            str(
                data["workspace_id"]
            )
        )

        publication_id = UUID(
            str(
                data["publication_id"]
            )
        )

        user_id = UUID(
            str(
                data["user_id"]
            )
        )

        content_hash = str(
            data["content_hash"]
        )

        issued_at = int(
            data["issued_at"]
        )

    except Exception as exc:
        raise PublicationActivationInvalid(
            "Publication activation payload is invalid"
        ) from exc

    _validate_content_hash(
        content_hash
    )

    now = int(
        time.time()
    )

    if issued_at > now + 30:
        raise PublicationActivationInvalid(
            "Publication activation issued_at is invalid"
        )

    if (
        now - issued_at
        > PUBLICATION_ACTIVATION_TTL_SECONDS
    ):
        raise PublicationActivationExpired(
            "Publication activation expired"
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
        raise PublicationActivationInvalid(
            "Publication activation binding mismatch"
        )

    return PublicationActivationPayload(
        workspace_id=workspace_id,
        publication_id=publication_id,
        user_id=user_id,
        content_hash=content_hash,
        issued_at=issued_at,
    )
