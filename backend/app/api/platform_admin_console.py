from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.platform_admin_access import (
    require_platform_admin_read,
)
from app.core.database import get_db
from app.models.commercial import PlatformAdminMembership
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.commercial import (
    PlatformAdminIdentityResponse,
    PlatformAdminWorkspaceListResponse,
    PlatformAdminWorkspaceResponse,
)


router = APIRouter(
    prefix="/api/platform-admin",
    tags=["Platform Administration"],
)


@router.get(
    "/me",
    response_model=PlatformAdminIdentityResponse,
)
async def platform_admin_me(
    current_user: User = Depends(get_current_user),
    admin: PlatformAdminMembership = Depends(
        require_platform_admin_read
    ),
):
    return PlatformAdminIdentityResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=admin.role,
    )


@router.get(
    "/workspaces",
    response_model=PlatformAdminWorkspaceListResponse,
)
async def read_platform_workspaces(
    q: str | None = Query(default=None, max_length=150),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: PlatformAdminMembership = Depends(
        require_platform_admin_read
    ),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    normalized_query = q.strip() if q is not None else ""
    if normalized_query:
        filters.append(
            or_(
                Workspace.name.contains(
                    normalized_query,
                    autoescape=True,
                ),
                Workspace.slug.contains(
                    normalized_query,
                    autoescape=True,
                ),
            )
        )

    total_result = await db.execute(
        select(func.count(Workspace.id)).where(*filters)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Workspace)
        .where(*filters)
        .order_by(
            Workspace.created_at.desc(),
            Workspace.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    workspaces = result.scalars().all()

    return PlatformAdminWorkspaceListResponse(
        items=[
            PlatformAdminWorkspaceResponse.model_validate(item)
            for item in workspaces
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
