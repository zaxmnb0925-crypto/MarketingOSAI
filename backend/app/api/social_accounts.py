import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import (
    require_workspace_delete,
    require_workspace_membership,
    require_workspace_write,
)
from app.core.database import get_db
from app.models.brand import Brand
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.social_account import (
    SocialAccountResponse,
    SocialAccountUpdate,
)


router = APIRouter(
    prefix=(
        "/api/workspaces/{workspace_id}"
        "/social-accounts"
    ),
    tags=["social-accounts"],
)


async def get_social_account_or_404(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    social_account_id: uuid.UUID,
) -> SocialAccount:
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id
            == social_account_id,
            SocialAccount.workspace_id
            == workspace_id,
        )
    )

    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Social account not found",
        )

    return account


async def validate_brand_workspace(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Brand.id).where(
            Brand.id == brand_id,
            Brand.workspace_id
            == workspace_id,
        )
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Brand does not belong "
                "to this workspace"
            ),
        )


@router.get(
    "",
    response_model=(
        list[SocialAccountResponse]
    ),
)
async def list_social_accounts(
    workspace_id: uuid.UUID,
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

    result = await db.execute(
        select(SocialAccount)
        .where(
            SocialAccount.workspace_id
            == workspace_id
        )
        .order_by(
            SocialAccount.created_at.desc()
        )
    )

    return list(
        result.scalars().all()
    )


@router.get(
    "/{social_account_id}",
    response_model=SocialAccountResponse,
)
async def get_social_account(
    workspace_id: uuid.UUID,
    social_account_id: uuid.UUID,
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

    return await get_social_account_or_404(
        db,
        workspace_id,
        social_account_id,
    )


@router.patch(
    "/{social_account_id}",
    response_model=SocialAccountResponse,
)
async def update_social_account(
    workspace_id: uuid.UUID,
    social_account_id: uuid.UUID,
    payload: SocialAccountUpdate,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    account = await get_social_account_or_404(
        db,
        workspace_id,
        social_account_id,
    )

    updates = payload.model_dump(
        exclude_unset=True
    )

    if (
        "brand_id" in updates
        and updates["brand_id"] is not None
    ):
        await validate_brand_workspace(
            db,
            workspace_id,
            updates["brand_id"],
        )

    for key, value in updates.items():
        setattr(
            account,
            key,
            value,
        )

    await db.commit()
    await db.refresh(account)

    return account


@router.delete(
    "/{social_account_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
)
async def delete_social_account(
    workspace_id: uuid.UUID,
    social_account_id: uuid.UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_delete(
        db,
        current_user,
        workspace_id,
    )

    account = await get_social_account_or_404(
        db,
        workspace_id,
        social_account_id,
    )

    await db.delete(account)
    await db.commit()

    return Response(
        status_code=(
            status.HTTP_204_NO_CONTENT
        )
    )
