from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import (
    require_workspace_membership,
)
from app.core.database import get_db
from app.models.user import User
from app.schemas.usage import WorkspaceUsageResponse
from app.services.usage_analytics import (
    get_workspace_usage,
)


router = APIRouter(
    prefix="/api/workspaces",
    tags=["usage"],
)


@router.get(
    "/{workspace_id}/usage",
    response_model=WorkspaceUsageResponse,
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
