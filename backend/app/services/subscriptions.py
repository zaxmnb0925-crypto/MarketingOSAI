import calendar
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_credit import WorkspaceCreditAccount
from app.models.subscription import (
    SubscriptionPlan,
    WorkspaceSubscription,
)


REQUIRED_CATALOG_PLAN_CODES = (
    "free",
    "pro",
    "business",
)


class SubscriptionCatalogConfigurationError(RuntimeError):
    pass


class SubscriptionStateError(RuntimeError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def add_one_month(value: datetime) -> datetime:
    year = value.year
    month = value.month + 1
    if month == 13:
        month = 1
        year += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


async def ensure_default_plans(db: AsyncSession) -> None:
    """Verify the migration-owned catalog without mutating it."""
    result = await db.execute(
        select(SubscriptionPlan.code).where(
            SubscriptionPlan.code.in_(REQUIRED_CATALOG_PLAN_CODES)
        )
    )
    missing = set(REQUIRED_CATALOG_PLAN_CODES) - set(result.scalars().all())
    if missing:
        raise SubscriptionCatalogConfigurationError(
            "Required subscription catalog is not configured"
        )


async def get_plan(
    db: AsyncSession,
    plan_code: str,
) -> SubscriptionPlan | None:
    await ensure_default_plans(db)
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code)
    )
    return result.scalar_one_or_none()


async def get_selectable_plan(
    db: AsyncSession,
    plan_code: str,
) -> SubscriptionPlan | None:
    plan = await get_plan(db, plan_code)
    if plan is None or not plan.is_active or not plan.is_public:
        return None
    return plan


async def provision_free_subscription(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    account: WorkspaceCreditAccount | None = None,
    now: datetime | None = None,
) -> tuple[WorkspaceSubscription, SubscriptionPlan]:
    """Idempotently provision the non-expiring Free commercial aggregate."""
    await ensure_default_plans(db)
    free = await get_plan(db, "free")
    if (
        free is None
        or not free.is_active
        or not free.is_public
        or free.list_price_minor != 0
        or free.currency != "TWD"
    ):
        raise SubscriptionCatalogConfigurationError(
            "Free subscription catalog is invalid"
        )
    timestamp = now or utcnow()
    accounting_end = add_one_month(timestamp)
    inserted = await db.execute(
        insert(WorkspaceSubscription)
        .values(
            workspace_id=workspace_id,
            plan_code="free",
            status="active",
            starts_at=timestamp,
            expires_at=None,
            activated_at=timestamp,
            activated_by_user_id=None,
            suspended_at=None,
            cancelled_at=None,
            cancellation_effective_at=None,
            source="system",
            entitlement_version=1,
            renewal_price_minor=0,
            billing_currency="TWD",
            pricing_source="free",
            cycle_start=timestamp,
            cycle_end=accounting_end,
            credits_granted=free.monthly_credits,
            credits_used=0,
            auto_renew=True,
            created_at=timestamp,
            updated_at=timestamp,
        )
        .on_conflict_do_nothing(index_elements=["workspace_id"])
        .returning(WorkspaceSubscription.workspace_id)
    )
    created = inserted.scalar_one_or_none() is not None
    result = await db.execute(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id
        )
    )
    subscription = result.scalar_one()
    if subscription.plan_code == "free" and subscription.expires_at is not None:
        raise SubscriptionStateError("Free subscription has a commercial expiry")

    if account is None:
        await db.execute(
            insert(WorkspaceCreditAccount)
            .values(
                workspace_id=workspace_id,
                balance=free.monthly_credits if created else 0,
                lifetime_used=0,
                created_at=timestamp,
                updated_at=timestamp,
            )
            .on_conflict_do_nothing(index_elements=["workspace_id"])
        )
        account_result = await db.execute(
            select(WorkspaceCreditAccount).where(
                WorkspaceCreditAccount.workspace_id == workspace_id
            )
        )
        account = account_result.scalar_one()

    if created:
        account.balance = free.monthly_credits
        account.updated_at = timestamp
    await db.flush()
    return subscription, free


async def ensure_subscription_cycle(
    db: AsyncSession,
    workspace_id: UUID,
    account: WorkspaceCreditAccount,
    *,
    lock: bool = False,
):
    """Maintain only the legacy AI-credit cycle, never paid commercial time."""
    await ensure_default_plans(db)
    query = select(WorkspaceSubscription).where(
        WorkspaceSubscription.workspace_id == workspace_id
    )
    if lock:
        query = query.with_for_update()
    result = await db.execute(query)
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return await provision_free_subscription(
            db,
            workspace_id,
            account=account,
        )

    plan = await get_plan(db, subscription.plan_code)
    if plan is None:
        raise SubscriptionCatalogConfigurationError(
            "Subscription plan is not configured"
        )
    if subscription.plan_code == "free":
        if subscription.expires_at is not None:
            raise SubscriptionStateError("Free subscription has a commercial expiry")
    elif subscription.expires_at is None:
        raise SubscriptionStateError("Paid subscription has no commercial expiry")

    now = utcnow()
    if now >= subscription.cycle_end:
        # cycle_* and legacy credit balance are accounting compatibility only.
        # Never copy cycle_end into commercial expires_at.
        subscription.cycle_start = now
        subscription.cycle_end = add_one_month(now)
        subscription.credits_granted = plan.monthly_credits
        subscription.credits_used = 0
        subscription.updated_at = now
        account.balance = plan.monthly_credits
        account.updated_at = now
    return subscription, plan
