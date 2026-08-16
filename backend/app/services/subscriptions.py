import calendar
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    SubscriptionPlan,
    WorkspaceSubscription,
)


PLAN_DEFINITIONS = [
    {
        "code": "free",
        "name": "Free",
        "price_twd": 0,
        "monthly_credits": 20,
    },
    {
        "code": "starter",
        "name": "Starter",
        "price_twd": 590,
        "monthly_credits": 300,
    },
    {
        "code": "pro",
        "name": "Pro",
        "price_twd": 1490,
        "monthly_credits": 1000,
    },
    {
        "code": "business",
        "name": "Business",
        "price_twd": 2990,
        "monthly_credits": 2500,
    },
    {
        "code": "agency",
        "name": "Agency",
        "price_twd": 6990,
        "monthly_credits": 7500,
    },
]


def utcnow():
    return datetime.now(timezone.utc)


def add_one_month(value: datetime) -> datetime:
    year = value.year
    month = value.month + 1

    if month == 13:
        month = 1
        year += 1

    max_day = calendar.monthrange(
        year,
        month,
    )[1]

    day = min(
        value.day,
        max_day,
    )

    return value.replace(
        year=year,
        month=month,
        day=day,
    )


async def ensure_default_plans(
    db: AsyncSession,
) -> None:

    for plan in PLAN_DEFINITIONS:

        stmt = (
            insert(SubscriptionPlan)
            .values(
                **plan,
                is_active=True,
                created_at=utcnow(),
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "name": plan["name"],
                    "price_twd": plan["price_twd"],
                    "monthly_credits": (
                        plan["monthly_credits"]
                    ),
                    "is_active": True,
                },
            )
        )

        await db.execute(stmt)


async def get_plan(
    db: AsyncSession,
    plan_code: str,
) -> SubscriptionPlan | None:

    await ensure_default_plans(db)

    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.code
            == plan_code
        )
    )

    return result.scalar_one_or_none()


async def ensure_subscription_cycle(
    db: AsyncSession,
    workspace_id: UUID,
    account,
    *,
    lock: bool = False,
):
    await ensure_default_plans(db)

    query = select(
        WorkspaceSubscription
    ).where(
        WorkspaceSubscription.workspace_id
        == workspace_id
    )

    if lock:
        query = query.with_for_update()

    result = await db.execute(query)

    subscription = (
        result.scalar_one_or_none()
    )

    now = utcnow()

    if subscription is None:

        plan = await get_plan(
            db,
            "free",
        )

        cycle_end = add_one_month(now)

        subscription = WorkspaceSubscription(
            workspace_id=workspace_id,
            plan_code="free",
            status="active",
            cycle_start=now,
            cycle_end=cycle_end,
            credits_granted=(
                plan.monthly_credits
            ),
            credits_used=0,
            auto_renew=True,
            created_at=now,
            updated_at=now,
        )

        db.add(subscription)

        account.balance = (
            plan.monthly_credits
        )

        account.updated_at = now

        await db.flush()

        return subscription, plan

    plan = await get_plan(
        db,
        subscription.plan_code,
    )

    if now >= subscription.cycle_end:

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

    return subscription, plan
