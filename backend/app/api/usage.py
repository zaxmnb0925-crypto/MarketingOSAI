from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.platform_admin_access import (
    require_platform_admin_accounting_read,
)
from app.api.workspace_access import (
    require_workspace_membership,
)
from app.core.database import get_db
from app.models.commercial import PlatformAdminMembership
from app.models.user import User
from app.schemas.usage import (
    CustomerWorkspaceUsageResponse,
    WorkspaceUsageResponse,
)
from app.services.usage_analytics import (
    get_workspace_usage,
)


router = APIRouter(
    prefix="/api/workspaces",
    tags=["usage"],
)

platform_admin_router = APIRouter(
    prefix="/api/platform-admin/workspaces",
    tags=["Platform AI Accounting"],
)


@router.get(
    "/{workspace_id}/usage",
    response_model=CustomerWorkspaceUsageResponse,
)
async def workspace_usage(
    workspace_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(
        db,
        current_user,
        workspace_id,
    )

    return await get_workspace_usage(
        db,
        workspace_id,
    )


@platform_admin_router.get(
    "/{workspace_id}/usage",
    response_model=WorkspaceUsageResponse,
)
async def platform_admin_workspace_usage(
    workspace_id: UUID,
    admin: PlatformAdminMembership = Depends(
        require_platform_admin_accounting_read
    ),
    db: AsyncSession = Depends(get_db),
):
    return await get_workspace_usage(db, workspace_id)
