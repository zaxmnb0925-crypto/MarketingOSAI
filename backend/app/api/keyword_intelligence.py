from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import require_workspace_membership
from app.core.database import get_db
from app.models.user import User
from app.schemas.keyword_intelligence import (
    KeywordTrendQueryParameters,
    KeywordTrendSignalListResponse,
)
from app.services.keyword_intelligence import list_keyword_trend_signals


router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/keyword-signals",
    tags=["Keyword Intelligence"],
)


@router.get("", response_model=KeywordTrendSignalListResponse)
async def read_keyword_trend_signals(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    platform: Annotated[str | None, Query(max_length=40)] = None,
    region: Annotated[str | None, Query(max_length=16)] = None,
    language: Annotated[str | None, Query(max_length=20)] = None,
    query: Annotated[str | None, Query(max_length=100)] = None,
    include_stale: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
):
    await require_workspace_membership(db, current_user, workspace_id)
    parameters = KeywordTrendQueryParameters(
        platform=platform,
        region=region,
        language=language,
        query=query,
        include_stale=include_stale,
        limit=limit,
    )
    return await list_keyword_trend_signals(
        db,
        workspace_id,
        parameters,
    )
