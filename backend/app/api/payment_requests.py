from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import require_workspace_membership
from app.core.database import get_db
from app.models.payment_request import PaymentRequest
from app.models.subscription import SubscriptionPlan
from app.models.user import User
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestResponse,
    AdminPaymentRequestResponse,
)


router = APIRouter(tags=["Payment Requests"])


@router.post(
    "/api/workspaces/{workspace_id}/payment-requests",
    response_model=PaymentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_request(
    workspace_id: UUID,
    payload: PaymentRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)

    plan_code = payload.requested_plan_code.strip().lower()
    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.code == plan_code,
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.is_public.is_(True),
        )
    )
    if plan_result.scalar_one_or_none() is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Public subscription plan not found",
        )

    duplicate_result = await db.execute(
        select(PaymentRequest).where(
            PaymentRequest.workspace_id == workspace_id,
            PaymentRequest.requested_plan_code == plan_code,
            PaymentRequest.status.in_(
                ["requested", "payment_pending"]
            ),
        )
    )

    if duplicate_result.first() is not None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active request for this plan already exists",
        )

    request = PaymentRequest(
        workspace_id=workspace_id,
        requested_plan_code=plan_code,
        customer_note=payload.customer_note,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return PaymentRequestResponse.model_validate(request)


@router.get(
    "/api/workspaces/{workspace_id}/payment-requests",
    response_model=list[PaymentRequestResponse],
)
async def list_payment_requests(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)

    result = await db.execute(
        select(PaymentRequest)
        .where(PaymentRequest.workspace_id == workspace_id)
        .order_by(PaymentRequest.created_at.desc())
    )
    return [
        PaymentRequestResponse.model_validate(item)
        for item in result.scalars().all()
    ]


@router.get(
    "/api/platform-admin/payment-requests",
    response_model=list[AdminPaymentRequestResponse],
)
async def platform_admin_payment_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.api.platform_admin_access import require_platform_admin_payment_read
    from app.models.membership import Membership, MembershipRole
    from app.models.workspace import Workspace
    from app.schemas.payment_request import AdminPaymentRequestResponse

    await require_platform_admin_payment_read(current_user, db)

    result = await db.execute(
        select(PaymentRequest, Workspace, User)
        .join(Workspace, Workspace.id == PaymentRequest.workspace_id)
        .join(
            Membership,
            Membership.workspace_id == Workspace.id,
        )
        .join(User, User.id == Membership.user_id)
        .where(Membership.role == MembershipRole.owner)
        .order_by(PaymentRequest.created_at.desc())
    )

    return [
        AdminPaymentRequestResponse(
            **PaymentRequestResponse.model_validate(request).model_dump(),
            workspace_name=workspace.name,
            owner_email=owner.email,
            owner_full_name=owner.full_name,
        )
        for request, workspace, owner in result.all()
    ]
