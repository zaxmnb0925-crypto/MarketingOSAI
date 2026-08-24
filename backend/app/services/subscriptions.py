import calendar
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    SubscriptionPlan,
    WorkspaceSubscription,
)


REQUIRED_CATALOG_PLAN_CODES = (
    "free",
    "pro",
    "business",
)


class SubscriptionCatalogConfigurationError(
    RuntimeError
):
    pass


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
    """
    Verify the migration-owned catalog invariant.

    Retain the historical function name for current
    callers while removing all request-time catalog
    insertion and price mutation.
    """
    result = await db.execute(
        select(SubscriptionPlan.code).where(
            SubscriptionPlan.code.in_(
                REQUIRED_CATALOG_PLAN_CODES
            )
        )
    )

    available = set(
        result.scalars().all()
    )

    missing = (
        set(REQUIRED_CATALOG_PLAN_CODES)
        - available
    )

    if missing:
        raise SubscriptionCatalogConfigurationError(
            "Required subscription catalog "
            "is not configured"
        )


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

        #
        # Transitional compatibility only:
        # deterministic registration-time provisioning
        # moves to P2. Existing lazy cycle creation remains
        # until that patch, but the Plan row itself must
        # already exist from the migration.
        #
        subscription = WorkspaceSubscription(
            workspace_id=workspace_id,
            plan_code="free",
            status="active",
            starts_at=now,
            expires_at=cycle_end,
            activated_at=now,
            source="system",
            entitlement_version=1,
            renewal_price_minor=0,
            billing_currency="TWD",
            pricing_source="free",
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
        subscription.expires_at = (
            subscription.cycle_end
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
