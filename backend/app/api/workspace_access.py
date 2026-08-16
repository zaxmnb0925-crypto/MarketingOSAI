from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import Membership, MembershipRole
from app.models.user import User


WRITE_ROLES = {
    MembershipRole.owner,
    MembershipRole.admin,
    MembershipRole.manager,
    MembershipRole.editor,
}

#
# External publishing creates a provider-side side effect.
# It intentionally uses a narrower permission set than
# ordinary Workspace writes.
#
PUBLISH_ROLES = {
    MembershipRole.owner,
    MembershipRole.admin,
    MembershipRole.manager,
}

DELETE_ROLES = {
    MembershipRole.owner,
    MembershipRole.admin,
}


async def require_workspace_membership(
    db: AsyncSession,
    user: User,
    workspace_id: UUID,
) -> Membership:

    result = await db.execute(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )

    membership = result.scalar_one_or_none()

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workspace",
        )

    return membership


async def require_workspace_write(
    db: AsyncSession,
    user: User,
    workspace_id: UUID,
) -> Membership:

    membership = await require_workspace_membership(
        db,
        user,
        workspace_id,
    )

    if membership.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace permission",
        )

    return membership


async def require_workspace_publish(
    db: AsyncSession,
    user: User,
    workspace_id: UUID,
) -> Membership:
    membership = await require_workspace_membership(
        db,
        user,
        workspace_id,
    )

    if membership.role not in PUBLISH_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient publishing permission",
        )

    return membership


async def require_workspace_delete(
    db: AsyncSession,
    user: User,
    workspace_id: UUID,
) -> Membership:

    membership = await require_workspace_membership(
        db,
        user,
        workspace_id,
    )

    if membership.role not in DELETE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace permission",
        )

    return membership
