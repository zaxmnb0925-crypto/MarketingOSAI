from .common import (
    Publication,
    PublicationStateError,
    hashlib,
)

def content_sha256(
    content: str,
) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


def verify_snapshot_integrity(
    publication: Publication,
) -> None:
    if (
        not publication.content_snapshot
        or not publication.content_snapshot.strip()
    ):
        raise PublicationStateError(
            "Publication content snapshot is empty"
        )

    actual_hash = content_sha256(
        publication.content_snapshot
    )

    if actual_hash != publication.content_hash:
        raise PublicationStateError(
            "Publication content snapshot "
            "integrity check failed"
        )
