from uuid import UUID

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
from app.models.user import User
from app.schemas.brand import (
    BrandCreate,
    BrandResponse,
    BrandUpdate,
)


router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/brands",
    tags=["Brands"],
)


def serialize_brand(brand: Brand) -> BrandResponse:
    return BrandResponse(
        id=brand.id,
        workspace_id=brand.workspace_id,
        name=brand.name,
        industry=brand.industry,
        website=brand.website,
        description=brand.description,
        tone=brand.tone,
        target_audience=brand.target_audience,
        brand_voice=brand.brand_voice,
        value_proposition=brand.value_proposition,
        products_services=brand.products_services,
        keywords=brand.keywords,
        forbidden_words=brand.forbidden_words,
        default_cta=brand.default_cta,
        language=brand.language,
        country=brand.country,
        brand_guidelines=brand.brand_guidelines,
    )


@router.get(
    "",
    response_model=list[BrandResponse],
)
async def list_brands(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_membership(
        db,
        current_user,
        workspace_id,
    )

    result = await db.execute(
        select(Brand)
        .where(
            Brand.workspace_id == workspace_id
        )
        .order_by(Brand.created_at.desc())
    )

    brands = result.scalars().all()

    return [
        serialize_brand(brand)
        for brand in brands
    ]


@router.post(
    "",
    response_model=BrandResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_brand(
    workspace_id: UUID,
    payload: BrandCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    brand = Brand(
        workspace_id=workspace_id,
        name=payload.name.strip(),
        industry=(
            payload.industry.strip()
            if payload.industry
            else None
        ),
        website=(
            str(payload.website)
            if payload.website
            else None
        ),
        description=payload.description,
        tone=(
            payload.tone.strip()
            if payload.tone
            else None
        ),
        target_audience=payload.target_audience,
        brand_voice=payload.brand_voice,
        value_proposition=payload.value_proposition,
        products_services=payload.products_services,
        keywords=payload.keywords,
        forbidden_words=payload.forbidden_words,
        default_cta=payload.default_cta,
        language=payload.language,
        country=payload.country,
        brand_guidelines=payload.brand_guidelines,
    )

    db.add(brand)
    await db.commit()
    await db.refresh(brand)

    return serialize_brand(brand)


@router.get(
    "/{brand_id}",
    response_model=BrandResponse,
)
async def get_brand(
    workspace_id: UUID,
    brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_membership(
        db,
        current_user,
        workspace_id,
    )

    result = await db.execute(
        select(Brand).where(
            Brand.id == brand_id,
            Brand.workspace_id == workspace_id,
        )
    )

    brand = result.scalar_one_or_none()

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    return serialize_brand(brand)


@router.patch(
    "/{brand_id}",
    response_model=BrandResponse,
)
async def update_brand(
    workspace_id: UUID,
    brand_id: UUID,
    payload: BrandUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    result = await db.execute(
        select(Brand).where(
            Brand.id == brand_id,
            Brand.workspace_id == workspace_id,
        )
    )

    brand = result.scalar_one_or_none()

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    updates = payload.model_dump(
        exclude_unset=True
    )

    if "website" in updates:
        updates["website"] = (
            str(updates["website"])
            if updates["website"]
            else None
        )

    if "name" in updates and updates["name"]:
        updates["name"] = updates["name"].strip()

    if "industry" in updates and updates["industry"]:
        updates["industry"] = updates["industry"].strip()

    if "tone" in updates and updates["tone"]:
        updates["tone"] = updates["tone"].strip()

    for field, value in updates.items():
        setattr(
            brand,
            field,
            value,
        )

    await db.commit()
    await db.refresh(brand)

    return serialize_brand(brand)


@router.delete(
    "/{brand_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_brand(
    workspace_id: UUID,
    brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_delete(
        db,
        current_user,
        workspace_id,
    )

    result = await db.execute(
        select(Brand).where(
            Brand.id == brand_id,
            Brand.workspace_id == workspace_id,
        )
    )

    brand = result.scalar_one_or_none()

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    await db.delete(brand)
    await db.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
