"""Real PostgreSQL validation for P5-C1 keyword intelligence."""

from datetime import datetime, timedelta, timezone
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _integration_run_identity import integration_token, integration_uuid
from app.schemas.keyword_intelligence import KeywordTrendQueryParameters
from app.services.keyword_intelligence import list_keyword_trend_signals


WORKSPACE_ID = integration_uuid("p5-c1-keyword-workspace")
OTHER_WORKSPACE_ID = integration_uuid("p5-c1-keyword-other-workspace")
FRESH_ID = integration_uuid("p5-c1-keyword-fresh")
STALE_ID = integration_uuid("p5-c1-keyword-stale")
OTHER_ID = integration_uuid("p5-c1-keyword-other")
RUN_TOKEN = integration_token("p5-c1-keyword")
NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)

engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def cleanup() -> None:
    async with Session.begin() as db:
        await db.execute(
            text(
                "DELETE FROM keyword_trend_signals "
                "WHERE workspace_id = ANY(:ids)"
            ),
            {"ids": [WORKSPACE_ID, OTHER_WORKSPACE_ID]},
        )
        await db.execute(
            text("DELETE FROM workspaces WHERE id = ANY(:ids)"),
            {"ids": [WORKSPACE_ID, OTHER_WORKSPACE_ID]},
        )


async def setup() -> None:
    await cleanup()
    async with Session.begin() as db:
        for workspace_id, suffix in (
            (WORKSPACE_ID, "primary"),
            (OTHER_WORKSPACE_ID, "other"),
        ):
            await db.execute(
                text(
                    "INSERT INTO workspaces (id,name,slug,created_at) "
                    "VALUES (:id,:name,:slug,:created_at)"
                ),
                {
                    "id": workspace_id,
                    "name": f"{RUN_TOKEN}-{suffix}",
                    "slug": f"{RUN_TOKEN}-{suffix}",
                    "created_at": NOW,
                },
            )

        rows = (
            (
                FRESH_ID,
                WORKSPACE_ID,
                "AI 行銷",
                "ai 行銷",
                92.0,
                NOW + timedelta(hours=1),
            ),
            (
                STALE_ID,
                WORKSPACE_ID,
                "過期趨勢",
                "過期趨勢",
                80.0,
                NOW,
            ),
            (
                OTHER_ID,
                OTHER_WORKSPACE_ID,
                "其他客戶私有關鍵字",
                "其他客戶私有關鍵字",
                99.0,
                NOW + timedelta(hours=1),
            ),
        )
        for signal_id, workspace_id, keyword, normalized, score, expires in rows:
            await db.execute(
                text(
                    """
                    INSERT INTO keyword_trend_signals (
                        id,workspace_id,keyword,normalized_keyword,platform,
                        region,language,source_name,source_type,score,rank,
                        momentum,evidence_note,observed_at,expires_at,created_at
                    ) VALUES (
                        :id,:workspace_id,:keyword,:normalized,'google_search',
                        'TW','zh-TW','Synthetic integration fixture','synthetic',
                        :score,1,'rising','Test-only evidence',
                        :observed_at,:expires_at,:created_at
                    )
                    """
                ),
                {
                    "id": signal_id,
                    "workspace_id": workspace_id,
                    "keyword": keyword,
                    "normalized": normalized,
                    "score": score,
                    "observed_at": NOW - timedelta(minutes=30),
                    "expires_at": expires,
                    "created_at": NOW - timedelta(minutes=30),
                },
            )


async def snapshot() -> tuple[tuple, ...]:
    async with Session() as db:
        result = await db.execute(
            text(
                """
                SELECT id::text,workspace_id::text,keyword,score,expires_at
                FROM keyword_trend_signals
                WHERE workspace_id = ANY(:ids)
                ORDER BY id
                """
            ),
            {"ids": [WORKSPACE_ID, OTHER_WORKSPACE_ID]},
        )
        return tuple(tuple(row) for row in result)


@pytest.mark.asyncio
async def test_p5_c1_real_postgresql_keyword_read_contract() -> None:
    await setup()
    try:
        before = await snapshot()
        async with Session() as db:
            fresh = await list_keyword_trend_signals(
                db,
                WORKSPACE_ID,
                KeywordTrendQueryParameters(),
                now=NOW,
            )
            assert [item.id for item in fresh.items] == [FRESH_ID]
            assert fresh.items[0].stale is False

            all_signals = await list_keyword_trend_signals(
                db,
                WORKSPACE_ID,
                KeywordTrendQueryParameters(include_stale=True),
                now=NOW,
            )
            assert [item.id for item in all_signals.items] == [FRESH_ID, STALE_ID]
            assert [item.stale for item in all_signals.items] == [False, True]
            assert OTHER_ID not in {item.id for item in all_signals.items}

            filtered = await list_keyword_trend_signals(
                db,
                WORKSPACE_ID,
                KeywordTrendQueryParameters(query="AI   行銷"),
                now=NOW,
            )
            assert [item.id for item in filtered.items] == [FRESH_ID]

        after = await snapshot()
        assert after == before
    finally:
        await cleanup()
        await engine.dispose()
