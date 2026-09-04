"""Real PostgreSQL validation for P5 platform-admin read models."""

from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _integration_run_identity import integration_token, integration_uuid
from app.api.platform_admin_console import read_platform_workspaces
from app.services.commercial_billing import list_payments


WORKSPACE_ALPHA_ID = integration_uuid("p5-admin-workspace-alpha")
WORKSPACE_BETA_ID = integration_uuid("p5-admin-workspace-beta")
WORKSPACE_OTHER_ID = integration_uuid("p5-admin-workspace-other")
PAYMENT_ALPHA_OLD_ID = integration_uuid("p5-admin-payment-alpha-old")
PAYMENT_ALPHA_MIDDLE_ID = integration_uuid("p5-admin-payment-alpha-middle")
PAYMENT_ALPHA_NEW_ID = integration_uuid("p5-admin-payment-alpha-new")
PAYMENT_BETA_ID = integration_uuid("p5-admin-payment-beta")
RUN_TOKEN = integration_token("p5-admin-read")
BASE_TIME = datetime(2026, 8, 28, 3, 0, tzinfo=timezone.utc)

engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def cleanup() -> None:
    async with Session.begin() as db:
        await db.execute(
            text("DELETE FROM payment_records WHERE workspace_id = ANY(:ids)"),
            {"ids": [WORKSPACE_ALPHA_ID, WORKSPACE_BETA_ID]},
        )
        await db.execute(
            text("DELETE FROM workspaces WHERE id = ANY(:ids)"),
            {
                "ids": [
                    WORKSPACE_ALPHA_ID,
                    WORKSPACE_BETA_ID,
                    WORKSPACE_OTHER_ID,
                ]
            },
        )


async def setup() -> None:
    await cleanup()
    async with Session.begin() as db:
        for workspace_id, name, slug, created_at in (
            (
                WORKSPACE_ALPHA_ID,
                f"{RUN_TOKEN} literal_%",
                f"{RUN_TOKEN}-literal-percent",
                BASE_TIME,
            ),
            (
                WORKSPACE_BETA_ID,
                f"{RUN_TOKEN} Beta",
                f"{RUN_TOKEN}-beta",
                BASE_TIME + timedelta(seconds=1),
            ),
            (
                WORKSPACE_OTHER_ID,
                "Unrelated Alpha wildcard candidate",
                f"{RUN_TOKEN}-other",
                BASE_TIME + timedelta(seconds=2),
            ),
        ):
            await db.execute(
                text(
                    "INSERT INTO workspaces (id,name,slug,created_at) "
                    "VALUES (:id,:name,:slug,:created_at)"
                ),
                {
                    "id": workspace_id,
                    "name": name,
                    "slug": slug,
                    "created_at": created_at,
                },
            )

        for workspace_id in (WORKSPACE_ALPHA_ID, WORKSPACE_BETA_ID):
            await db.execute(
                text(
                    """
                    INSERT INTO workspace_subscriptions (
                        workspace_id,plan_code,status,starts_at,expires_at,
                        activated_at,source,entitlement_version,
                        renewal_price_minor,billing_currency,pricing_source,
                        cycle_start,cycle_end,credits_granted,credits_used,
                        auto_renew,created_at,updated_at
                    ) VALUES (
                        :workspace_id,'free','active',:starts_at,NULL,
                        :starts_at,'system',1,0,'TWD',NULL,
                        :starts_at,:cycle_end,20,0,true,:starts_at,:starts_at
                    )
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "starts_at": BASE_TIME,
                    "cycle_end": BASE_TIME + timedelta(days=30),
                },
            )

        payments = (
            (
                PAYMENT_ALPHA_OLD_ID,
                WORKSPACE_ALPHA_ID,
                "pending",
                BASE_TIME + timedelta(minutes=1),
                "alpha-old",
            ),
            (
                PAYMENT_ALPHA_MIDDLE_ID,
                WORKSPACE_ALPHA_ID,
                "confirmed",
                BASE_TIME + timedelta(minutes=2),
                "alpha-middle",
            ),
            (
                PAYMENT_ALPHA_NEW_ID,
                WORKSPACE_ALPHA_ID,
                "pending",
                BASE_TIME + timedelta(minutes=3),
                "alpha-new",
            ),
            (
                PAYMENT_BETA_ID,
                WORKSPACE_BETA_ID,
                "pending",
                BASE_TIME + timedelta(minutes=4),
                "beta-only",
            ),
        )
        for payment_id, workspace_id, status, created_at, suffix in payments:
            await db.execute(
                text(
                    """
                    INSERT INTO payment_records (
                        id,workspace_id,source,method,amount_minor,currency,
                        status,received_at,idempotency_key,created_at,updated_at
                    ) VALUES (
                        :id,:workspace_id,'manual','bank',99000,'TWD',
                        :status,:created_at,:idempotency_key,:created_at,:created_at
                    )
                    """
                ),
                {
                    "id": payment_id,
                    "workspace_id": workspace_id,
                    "status": status,
                    "created_at": created_at,
                    "idempotency_key": f"{RUN_TOKEN}-{suffix}",
                },
            )


async def snapshot() -> tuple[tuple, ...]:
    async with Session() as db:
        result = await db.execute(
            text(
                """
                SELECT id::text,workspace_id::text,status,idempotency_key,
                       created_at
                FROM payment_records
                WHERE workspace_id = ANY(:ids)
                ORDER BY id
                """
            ),
            {"ids": [WORKSPACE_ALPHA_ID, WORKSPACE_BETA_ID]},
        )
        return tuple(tuple(row) for row in result)


async def assert_workspace_search_and_pagination() -> None:
    async with Session() as db:
        literal = await read_platform_workspaces(
            q="literal_%",
            limit=10,
            offset=0,
            admin=SimpleNamespace(role="support"),
            db=db,
        )
        assert literal.total == 1
        assert [item.id for item in literal.items] == [WORKSPACE_ALPHA_ID]

        page = await read_platform_workspaces(
            q=RUN_TOKEN,
            limit=1,
            offset=1,
            admin=SimpleNamespace(role="support"),
            db=db,
        )
        assert page.total == 3
        assert page.limit == 1
        assert page.offset == 1
        assert [item.id for item in page.items] == [WORKSPACE_BETA_ID]


async def assert_payment_scope_filter_and_pagination() -> None:
    async with Session() as db:
        page, total = await list_payments(
            db,
            WORKSPACE_ALPHA_ID,
            status=None,
            limit=1,
            offset=1,
        )
        assert total == 3
        assert [item.id for item in page] == [PAYMENT_ALPHA_MIDDLE_ID]

        pending, pending_total = await list_payments(
            db,
            WORKSPACE_ALPHA_ID,
            status="pending",
            limit=10,
            offset=0,
        )
        assert pending_total == 2
        assert [item.id for item in pending] == [
            PAYMENT_ALPHA_NEW_ID,
            PAYMENT_ALPHA_OLD_ID,
        ]
        assert all(item.workspace_id == WORKSPACE_ALPHA_ID for item in pending)
        assert PAYMENT_BETA_ID not in {item.id for item in pending}


@pytest.mark.asyncio
async def test_p5_real_postgresql_platform_admin_read_contract() -> None:
    await setup()
    try:
        before = await snapshot()
        await assert_workspace_search_and_pagination()
        await assert_payment_scope_filter_and_pagination()
        after = await snapshot()
        assert after == before
    finally:
        await cleanup()
        await engine.dispose()
