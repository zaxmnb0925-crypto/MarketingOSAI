"""Real PostgreSQL validation for the sealed P4 accounting contract."""

import asyncio
from decimal import Decimal
import os

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _integration_run_identity import integration_token, integration_uuid
from app.models.ai_credit import AICreditLedger, WorkspaceCreditAccount
from app.models.subscription import WorkspaceSubscription
from app.services.ai_credits import (
    AICreditAccountingConflict,
    get_or_create_credit_account,
    record_actual_cost,
    refund_credits,
    reserve_credits,
)


WORKSPACE_ID = integration_uuid("p4-accounting-workspace")
USER_ID = integration_uuid("p4-accounting-user")
BRAND_ID = integration_uuid("p4-accounting-brand")
ROLLBACK_ID = integration_uuid("p4-rollback-generation")
REFUND_ID = integration_uuid("p4-refund-generation")
COST_ID = integration_uuid("p4-cost-generation")
DEBIT_RACE_ID = integration_uuid("p4-debit-race-generation")
RUN_TOKEN = integration_token("p4-accounting")

engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def cleanup():
    async with Session.begin() as db:
        await db.execute(text("DELETE FROM workspaces WHERE id=:id"), {"id": WORKSPACE_ID})
        await db.execute(text("DELETE FROM users WHERE id=:id"), {"id": USER_ID})


async def setup():
    await cleanup()
    async with Session.begin() as db:
        await db.execute(text(
            "INSERT INTO users (id,email,is_active,created_at) "
            "VALUES (:id,:email,true,now())"
        ), {"id": USER_ID, "email": RUN_TOKEN + "@example.invalid"})
        await db.execute(text(
            "INSERT INTO workspaces (id,name,slug,created_at) "
            "VALUES (:id,:value,:value,now())"
        ), {"id": WORKSPACE_ID, "value": RUN_TOKEN})
        await db.execute(text(
            "INSERT INTO brands (id,workspace_id,name,language,created_at) "
            "VALUES (:id,:workspace_id,:name,'en',now())"
        ), {"id": BRAND_ID, "workspace_id": WORKSPACE_ID, "name": RUN_TOKEN})
        for generation_id, topic in (
            (ROLLBACK_ID, "rollback"), (REFUND_ID, "refund"),
            (COST_ID, "cost"), (DEBIT_RACE_ID, "debit-race"),
        ):
            await db.execute(text("""
                INSERT INTO content_generations (
                    id,workspace_id,brand_id,user_id,platform,topic,status,
                    created_at,updated_at
                ) VALUES (
                    :id,:workspace_id,:brand_id,:user_id,'facebook',:topic,
                    'pending',now(),now()
                )
            """), {
                "id": generation_id, "workspace_id": WORKSPACE_ID,
                "brand_id": BRAND_ID, "user_id": USER_ID, "topic": topic,
            })


async def assert_indexes():
    async with Session() as db:
        result = await db.execute(text("""
            SELECT indexname,indexdef FROM pg_indexes
            WHERE schemaname=current_schema() AND indexname IN (
              'uq_ai_credit_ledger_generation_debit',
              'uq_ai_credit_ledger_generation_terminal_refund')
        """))
        rows = {row.indexname: row.indexdef for row in result}
    assert set(rows) == {
        "uq_ai_credit_ledger_generation_debit",
        "uq_ai_credit_ledger_generation_terminal_refund",
    }
    assert all("UNIQUE INDEX" in value for value in rows.values())
    assert all("generation_id IS NOT NULL" in value for value in rows.values())


async def assert_null_generation_unaffected():
    async with Session.begin() as db:
        for label in ("one", "two"):
            await db.execute(text("""
                INSERT INTO ai_credit_ledger (
                    id,workspace_id,generation_id,operation,credits,created_at
                ) VALUES (:id,:workspace_id,NULL,'content_generation',-1,now())
            """), {
                "id": integration_uuid("p4-null-ledger-" + label),
                "workspace_id": WORKSPACE_ID,
            })


async def assert_caller_rollback_is_atomic():
    async with Session() as db:
        account = await get_or_create_credit_account(db, WORKSPACE_ID, lock=True)
        await db.commit()
        initial = (account.balance, account.lifetime_used)
    async with Session() as db:
        await reserve_credits(db, WORKSPACE_ID, 1, generation_id=ROLLBACK_ID)
        await db.rollback()
    async with Session() as db:
        account = await db.get(WorkspaceCreditAccount, WORKSPACE_ID)
        subscription = await db.get(WorkspaceSubscription, WORKSPACE_ID)
        count = await db.scalar(select(func.count()).select_from(AICreditLedger).where(
            AICreditLedger.generation_id == ROLLBACK_ID
        ))
        assert (account.balance, account.lifetime_used) == initial
        assert subscription.credits_used == 0
        assert count == 0


async def assert_concurrent_terminal_refund():
    async with Session() as db:
        account = await db.get(WorkspaceCreditAccount, WORKSPACE_ID)
        initial_balance = account.balance
        await reserve_credits(db, WORKSPACE_ID, 1, generation_id=REFUND_ID)
        await db.commit()

    async def contender(operation):
        async with Session() as db:
            try:
                await refund_credits(
                    db, WORKSPACE_ID, 1, generation_id=REFUND_ID,
                    operation=operation,
                )
                await db.commit()
                return "committed"
            except AICreditAccountingConflict:
                await db.rollback()
                return "conflict"

    outcomes = await asyncio.gather(
        contender("content_policy_refund"),
        contender("provider_failure_refund"),
    )
    assert sorted(outcomes) == ["committed", "conflict"]
    async with Session() as db:
        account = await db.get(WorkspaceCreditAccount, WORKSPACE_ID)
        count = await db.scalar(select(func.count()).select_from(AICreditLedger).where(
            AICreditLedger.generation_id == REFUND_ID,
            AICreditLedger.operation.in_((
                "content_policy_refund", "provider_failure_refund",
            )),
        ))
        assert account.balance == initial_balance
        assert count == 1


async def assert_concurrent_debit_unique():
    async def contender(label):
        async with Session() as db:
            try:
                await db.execute(text("""
                    INSERT INTO ai_credit_ledger (
                      id,workspace_id,generation_id,operation,credits,created_at
                    ) VALUES (
                      :id,:workspace_id,:generation_id,'content_generation',-1,now())
                """), {
                    "id": integration_uuid("p4-debit-race-" + label),
                    "workspace_id": WORKSPACE_ID, "generation_id": DEBIT_RACE_ID,
                })
                await db.commit()
                return "committed"
            except IntegrityError:
                await db.rollback()
                return "unique-conflict"
    outcomes = await asyncio.gather(contender("one"), contender("two"))
    assert sorted(outcomes) == ["committed", "unique-conflict"]


async def assert_actual_cost_write_once():
    async with Session() as db:
        _, debit = await reserve_credits(db, WORKSPACE_ID, 1, generation_id=COST_ID)
        debit_id = debit.id
        await record_actual_cost(db, debit_id, Decimal("0.125000"))
        await db.commit()
    async with Session() as db:
        await record_actual_cost(db, debit_id, Decimal("0.125000"))
        await db.commit()
    async with Session() as db:
        with pytest.raises(AICreditAccountingConflict):
            await record_actual_cost(db, debit_id, Decimal("0.250000"))
        await db.rollback()
    async with Session() as db:
        stored = await db.get(AICreditLedger, debit_id)
        assert stored.actual_cost_usd == Decimal("0.125000")


@pytest.mark.asyncio
async def test_p4_real_postgresql_accounting_contract():
    await setup()
    try:
        await assert_indexes()
        await assert_null_generation_unaffected()
        await assert_caller_rollback_is_atomic()
        await assert_concurrent_terminal_refund()
        await assert_concurrent_debit_unique()
        await assert_actual_cost_write_once()
    finally:
        await cleanup()
        await engine.dispose()
