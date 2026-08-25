from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_credit import (
    AICreditLedger,
    WorkspaceCreditAccount,
)
from app.models.subscription import (
    WorkspaceSubscription,
)
from app.services.subscriptions import (
    ensure_subscription_cycle,
)


INITIAL_CREDITS = 0
CONTENT_GENERATION_CREDITS = 1


def utcnow():
    return datetime.now(timezone.utc)


class InsufficientAICredits(Exception):
    pass


class AICreditAccountingConflict(Exception):
    pass


async def get_or_create_credit_account(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    lock: bool = False,
) -> WorkspaceCreditAccount:

    stmt = (
        insert(WorkspaceCreditAccount)
        .values(
            workspace_id=workspace_id,
            balance=INITIAL_CREDITS,
            lifetime_used=0,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        .on_conflict_do_nothing(
            index_elements=[
                "workspace_id"
            ]
        )
    )

    await db.execute(stmt)

    query = select(
        WorkspaceCreditAccount
    ).where(
        WorkspaceCreditAccount.workspace_id
        == workspace_id
    )

    if lock:
        query = query.with_for_update()

    result = await db.execute(query)

    account = result.scalar_one()

    await ensure_subscription_cycle(
        db,
        workspace_id,
        account,
        lock=lock,
    )

    return account


async def get_subscription_locked(
    db: AsyncSession,
    workspace_id: UUID,
):

    result = await db.execute(
        select(WorkspaceSubscription)
        .where(
            WorkspaceSubscription.workspace_id
            == workspace_id
        )
        .with_for_update()
    )

    return result.scalar_one()


async def _get_existing_generation_accounting_event(
    db: AsyncSession,
    workspace_id: UUID,
    generation_id: UUID | None,
    operations: tuple[str, ...],
    *,
    expected_credits: int,
):
    if generation_id is None:
        return None

    result = await db.execute(
        select(AICreditLedger)
        .where(
            AICreditLedger.workspace_id
            == workspace_id,
            AICreditLedger.generation_id
            == generation_id,
            AICreditLedger.operation.in_(operations),
        )
        .order_by(
            AICreditLedger.created_at.asc(),
            AICreditLedger.id.asc(),
        )
    )

    rows = list(
        result.scalars().all()
    )

    if not rows:
        return None

    if len(rows) != 1:
        raise AICreditAccountingConflict(
            "Multiple accounting events exist for one generation"
        )

    if any(
        int(row.credits)
        != expected_credits
        for row in rows
    ):
        raise AICreditAccountingConflict(
            "Accounting event already exists "
            "with a different credit amount"
        )

    return rows[0]


async def reserve_credits(
    db: AsyncSession,
    workspace_id: UUID,
    amount: int,
    *,
    generation_id: UUID | None = None,
    operation: str = "content_generation",
    note: str | None = None,
):

    if amount <= 0:
        raise ValueError(
            "Credit amount must be positive"
        )

    account = await get_or_create_credit_account(
        db,
        workspace_id,
        lock=True,
    )

    subscription = (
        await get_subscription_locked(
            db,
            workspace_id,
        )
    )

    existing_event = (
        await _get_existing_generation_accounting_event(
            db,
            workspace_id,
            generation_id,
            (operation,),
            expected_credits=-amount,
        )
    )

    if existing_event is not None:
        return account, existing_event

    if account.balance < amount:
        raise InsufficientAICredits(
            f"Need {amount} credits, "
            f"available {account.balance}"
        )

    account.balance -= amount
    account.lifetime_used += amount
    account.updated_at = utcnow()

    subscription.credits_used += amount
    subscription.updated_at = utcnow()

    ledger = AICreditLedger(
        workspace_id=workspace_id,
        generation_id=generation_id,
        operation=operation,
        credits=-amount,
        note=note,
    )

    db.add(ledger)
    await db.flush()

    return account, ledger


async def record_actual_cost(
    db: AsyncSession,
    ledger_id: UUID,
    actual_cost_usd: Decimal | float,
) -> None:

    result = await db.execute(
        select(AICreditLedger)
        .where(
            AICreditLedger.id
            == ledger_id
        )
        .with_for_update()
    )

    ledger = result.scalar_one()
    requested_cost = Decimal(str(actual_cost_usd))

    if ledger.actual_cost_usd is None:
        ledger.actual_cost_usd = requested_cost
        await db.flush()
        return

    if Decimal(ledger.actual_cost_usd) != requested_cost:
        raise AICreditAccountingConflict(
            "Actual provider cost is already recorded "
            "with a different value"
        )


async def refund_credits(
    db: AsyncSession,
    workspace_id: UUID,
    amount: int,
    *,
    generation_id: UUID | None = None,
    operation: str = "credit_refund",
    note: str | None = None,
):

    if amount <= 0:
        raise ValueError(
            "Refund amount must be positive"
        )

    account = await get_or_create_credit_account(
        db,
        workspace_id,
        lock=True,
    )

    subscription = (
        await get_subscription_locked(
            db,
            workspace_id,
        )
    )

    replay_operations = (
        (
            "content_policy_refund",
            "provider_failure_refund",
        )
        if operation in {
            "content_policy_refund",
            "provider_failure_refund",
        }
        else (operation,)
    )

    existing_event = (
        await _get_existing_generation_accounting_event(
            db,
            workspace_id,
            generation_id,
            replay_operations,
            expected_credits=amount,
        )
    )

    if existing_event is not None:
        if existing_event.operation != operation:
            raise AICreditAccountingConflict(
                "A terminal refund already exists "
                "for a different reason"
            )
        return account

    account.balance += amount

    account.lifetime_used = max(
        0,
        account.lifetime_used - amount,
    )

    account.updated_at = utcnow()

    subscription.credits_used = max(
        0,
        subscription.credits_used - amount,
    )

    subscription.updated_at = utcnow()

    ledger = AICreditLedger(
        workspace_id=workspace_id,
        generation_id=generation_id,
        operation=operation,
        credits=amount,
        note=note,
    )
    db.add(ledger)
    await db.flush()

    return account
