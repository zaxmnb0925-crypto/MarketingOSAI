from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import (
    require_workspace_delete,
    require_workspace_membership,
)
from app.core.database import get_db
from app.models.subscription import (
    SubscriptionPlan,
    WorkspaceSubscription,
)
from app.models.user import User
from app.schemas.subscription import (
    ChangePlanRequest,
    PlanResponse,
    WorkspaceSubscriptionResponse,
)
from app.services.ai_credits import (
    get_or_create_credit_account,
)
from app.services.subscriptions import (
    add_one_month,
    ensure_default_plans,
    ensure_subscription_cycle,
    get_plan,
)


router = APIRouter(
    tags=["Subscriptions"],
)


@router.get(
    "/api/subscription-plans",
    response_model=list[PlanResponse],
)
async def list_plans(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    await ensure_default_plans(db)

    await db.commit()

    result = await db.execute(
        select(SubscriptionPlan)
        .where(
            SubscriptionPlan.is_active.is_(
                True
            )
        )
        .order_by(
            SubscriptionPlan.price_twd
        )
    )

    return [
        PlanResponse(
            code=row.code,
            name=row.name,
            price_twd=row.price_twd,
            monthly_credits=(
                row.monthly_credits
            ),
            is_active=row.is_active,
        )
        for row in result.scalars().all()
    ]


@router.get(
    "/api/workspaces/{workspace_id}/subscription",
    response_model=WorkspaceSubscriptionResponse,
)
async def get_workspace_subscription(
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

    account = (
        await get_or_create_credit_account(
            db,
            workspace_id,
            lock=True,
        )
    )

    subscription, plan = (
        await ensure_subscription_cycle(
            db,
            workspace_id,
            account,
            lock=True,
        )
    )

    await db.commit()

    return WorkspaceSubscriptionResponse(
        workspace_id=workspace_id,
        plan_code=subscription.plan_code,
        plan_name=plan.name,
        price_twd=plan.price_twd,
        monthly_credits=(
            plan.monthly_credits
        ),
        balance=account.balance,
        lifetime_used=account.lifetime_used,
        credits_granted=(
            subscription.credits_granted
        ),
        credits_used=(
            subscription.credits_used
        ),
        cycle_start=(
            subscription.cycle_start
        ),
        cycle_end=subscription.cycle_end,
        status=subscription.status,
        auto_renew=subscription.auto_renew,
    )


@router.patch(
    "/api/workspaces/{workspace_id}/subscription",
    response_model=WorkspaceSubscriptionResponse,
)
async def change_workspace_plan(
    workspace_id: UUID,
    payload: ChangePlanRequest,
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

    plan = await get_plan(
        db,
        payload.plan_code.strip().lower(),
    )

    if (
        plan is None
        or not plan.is_active
    ):
        raise HTTPException(
            status_code=404,
            detail="Subscription plan not found",
        )

    account = (
        await get_or_create_credit_account(
            db,
            workspace_id,
            lock=True,
        )
    )

    result = await db.execute(
        select(WorkspaceSubscription)
        .where(
            WorkspaceSubscription.workspace_id
            == workspace_id
        )
        .with_for_update()
    )

    subscription = result.scalar_one()

    now = datetime.now(timezone.utc)

    if subscription.plan_code != plan.code:
        subscription.plan_code = plan.code
        subscription.status = "active"
        subscription.cycle_start = now
        subscription.cycle_end = (
            add_one_month(now)
        )
        subscription.credits_granted = (
            plan.monthly_credits
        )
        subscription.credits_used = 0
        subscription.updated_at = now

        account.balance = (
            plan.monthly_credits
        )
        account.updated_at = now

    await db.commit()

    return WorkspaceSubscriptionResponse(
        workspace_id=workspace_id,
        plan_code=subscription.plan_code,
        plan_name=plan.name,
        price_twd=plan.price_twd,
        monthly_credits=(
            plan.monthly_credits
        ),
        balance=account.balance,
        lifetime_used=account.lifetime_used,
        credits_granted=(
            subscription.credits_granted
        ),
        credits_used=(
            subscription.credits_used
        ),
        cycle_start=(
            subscription.cycle_start
        ),
        cycle_end=subscription.cycle_end,
        status=subscription.status,
        auto_renew=subscription.auto_renew,
    )
