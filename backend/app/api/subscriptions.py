from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import require_workspace_membership
from app.core.database import get_db
from app.models.subscription import SubscriptionPlan, WorkspaceSubscription
from app.models.user import User
from app.schemas.subscription import (
    ChangePlanRequest,
    CustomerWorkspaceSubscriptionResponse,
    PlanResponse,
)
from app.services.subscriptions import ensure_default_plans, get_plan


router = APIRouter(tags=["Subscriptions"])


@router.get(
    "/api/subscription-plans",
    response_model=list[PlanResponse],
)
async def list_plans(
    db: AsyncSession = Depends(get_db),
):
    await ensure_default_plans(db)
    result = await db.execute(
        select(SubscriptionPlan)
        .where(
            SubscriptionPlan.is_active.is_(True),
            SubscriptionPlan.is_public.is_(True),
        )
        .order_by(SubscriptionPlan.list_price_minor)
    )
    return [PlanResponse.model_validate(row) for row in result.scalars().all()]


@router.get(
    "/api/workspaces/{workspace_id}/subscription",
    response_model=CustomerWorkspaceSubscriptionResponse,
)
async def get_workspace_subscription(
    workspace_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    result = await db.execute(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id
        )
    )
    subscription = result.scalar_one()
    plan = await get_plan(db, subscription.plan_code)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Subscription catalog unavailable",
        )
    return CustomerWorkspaceSubscriptionResponse(
        workspace_id=workspace_id,
        plan_code=subscription.plan_code,
        plan_name=plan.name,
        cycle_start=subscription.cycle_start,
        cycle_end=subscription.cycle_end,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
        renewal_price_minor=subscription.renewal_price_minor,
        billing_currency=subscription.billing_currency,
        status=subscription.status,
        auto_renew=subscription.auto_renew,
    )


@router.patch(
    "/api/workspaces/{workspace_id}/subscription",
    status_code=status.HTTP_403_FORBIDDEN,
)
async def change_workspace_plan(
    workspace_id: UUID,
    payload: ChangePlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compatibility endpoint that deliberately closes customer mutation."""
    await require_workspace_membership(db, current_user, workspace_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Commercial changes require platform billing confirmation",
    )
