from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.platform_admin_access import (
    require_platform_admin_accounting_read,
)
from app.core.database import get_db
from app.models.commercial import PlatformAdminMembership
from app.schemas.usage import WorkspaceUsageResponse
from app.services.usage_analytics import (
    get_workspace_usage,
)


platform_admin_router = APIRouter(
    prefix="/api/platform-admin/workspaces",
    tags=["Platform AI Accounting"],
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
