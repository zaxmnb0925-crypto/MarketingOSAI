from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import require_workspace_membership
from app.core.database import get_db
from app.models.user import User
from app.schemas.keyword_intelligence import (
    KeywordTrendQueryParameters,
    KeywordSignalRefreshRequest,
    KeywordSignalRefreshResponse,
    KeywordTrendSignalListResponse,
)
from app.services.keyword_intelligence import (
    KeywordSignalProvider,
    list_keyword_trend_signals,
    refresh_keyword_trend_signals,
)


router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/keyword-signals",
    tags=["Keyword Intelligence"],
)


def get_keyword_signal_providers() -> tuple[KeywordSignalProvider, ...]:
    """P5-C2 keeps real provider wiring fail-closed."""
    return ()


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


@router.post(
    "/refresh",
    response_model=KeywordSignalRefreshResponse,
    status_code=status.HTTP_200_OK,
)
async def refresh_keyword_signals(
    workspace_id: UUID,
    request: KeywordSignalRefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    providers: tuple[KeywordSignalProvider, ...] = Depends(
        get_keyword_signal_providers
    ),
):
    await require_workspace_membership(db, current_user, workspace_id)
    if not providers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keyword signal providers are unavailable",
        )
    response = await refresh_keyword_trend_signals(
        db,
        workspace_id,
        platform=request.platform,
        region=request.region,
        language=request.language,
        providers=providers,
    )
    await db.commit()
    return response
