from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.workspace_access import (
    require_workspace_publish,
)
from app.models.membership import (
    Membership,
    MembershipRole,
)
from app.models.user import User


#
# Deliberately narrower than PUBLISH_ROLES.
#
# During the first-live-post safety phase, only an owner may
# issue and subsequently use a single-post activation grant.
#
PUBLICATION_ACTIVATION_ROLES = {
    MembershipRole.owner,
}


async def require_workspace_publish_activation(
    db: AsyncSession,
    user: User,
    workspace_id: UUID,
) -> Membership:
    #
    # First require ordinary publish permission. This makes
    # the activation permission structurally incapable of
    # being broader than /publish.
    #
    membership = await require_workspace_publish(
        db,
        user,
        workspace_id,
    )

    if (
        membership.role
        not in PUBLICATION_ACTIVATION_ROLES
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Insufficient publication "
                "activation permission"
            ),
        )

    return membership
