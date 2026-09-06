from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.platform_admin_access import require_platform_admin_read
from app.core.database import get_db
from app.models.support_inquiry import SupportInquiry
from app.models.user import User
from app.schemas.support_inquiry import (
    AdminSupportInquiryResponse,
    PublicSupportInquiryCreate,
    PublicSupportInquiryResponse,
)

router = APIRouter(tags=["support"])


@router.post(
    "/api/public/support/inquiries",
    response_model=PublicSupportInquiryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_public_support_inquiry(
    payload: PublicSupportInquiryCreate,
    db: AsyncSession = Depends(get_db),
) -> SupportInquiry:
    inquiry = SupportInquiry(
        email=str(payload.email).strip().lower(),
        category=payload.category,
        subject=payload.subject,
        message=payload.message,
        status="open",
        channel="web",
    )

    db.add(inquiry)
    await db.commit()
    await db.refresh(inquiry)

    return inquiry


@router.get(
    "/api/platform-admin/support/inquiries",
    response_model=list[AdminSupportInquiryResponse],
)
async def list_admin_support_inquiries(
    status_filter: str | None = Query(
        default=None,
        alias="status",
        max_length=32,
    ),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin_read),
) -> list[SupportInquiry]:
    query = select(SupportInquiry)

    if status_filter:
        query = query.where(
            SupportInquiry.status == status_filter.strip().lower(),
        )

    query = query.order_by(
        SupportInquiry.created_at.desc(),
    ).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())
