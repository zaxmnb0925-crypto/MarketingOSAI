from .common import (
    AsyncSession,
    Publication,
    PublicationNotFound,
    UUID,
    select,
)

async def _get_publication_for_update(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
) -> Publication:
    result = await db.execute(
        select(Publication)
        .where(
            Publication.id == publication_id,
            Publication.workspace_id
            == workspace_id,
        )
        .with_for_update()
    )

    publication = (
        result.scalar_one_or_none()
    )

    if publication is None:
        raise PublicationNotFound(
            "Publication not found"
        )

    return publication
