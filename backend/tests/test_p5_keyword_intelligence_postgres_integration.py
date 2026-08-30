"""Real PostgreSQL validation for P5-C1 keyword intelligence."""

from datetime import datetime, timedelta, timezone
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _integration_run_identity import integration_token, integration_uuid
from app.schemas.keyword_intelligence import (
    CollectiveKeywordQueryParameters,
    IntelligenceContextQueryParameters,
    KeywordTrendQueryParameters,
)
from app.services.keyword_intelligence import list_keyword_trend_signals
from app.services.keyword_intelligence import (
    ProviderKeywordSignal,
    assemble_intelligence_context,
    calculate_trend_score,
    list_collective_keyword_trends,
    refresh_keyword_trend_signals,
)


WORKSPACE_ID = integration_uuid("p5-c1-keyword-workspace")
OTHER_WORKSPACE_ID = integration_uuid("p5-c1-keyword-other-workspace")
FRESH_ID = integration_uuid("p5-c1-keyword-fresh")
STALE_ID = integration_uuid("p5-c1-keyword-stale")
OTHER_ID = integration_uuid("p5-c1-keyword-other")
COLLECTIVE_WORKSPACE_IDS = tuple(
    integration_uuid(f"p5-c3-collective-workspace-{index}")
    for index in range(1, 5)
)
RUN_TOKEN = integration_token("p5-c1-keyword")
NOW = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)

engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def cleanup() -> None:
    workspace_ids = [
        WORKSPACE_ID,
        OTHER_WORKSPACE_ID,
        *COLLECTIVE_WORKSPACE_IDS,
    ]
    async with Session.begin() as db:
        await db.execute(
            text(
                "DELETE FROM keyword_trend_signals "
                "WHERE workspace_id = ANY(:ids)"
            ),
            {"ids": workspace_ids},
        )
        await db.execute(
            text("DELETE FROM workspaces WHERE id = ANY(:ids)"),
            {"ids": workspace_ids},
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


class DeterministicPostgresProvider:
    provider_name = "p5_c2_deterministic_postgres"

    def __init__(self, signals):
        self.signals = list(signals)
        self.calls = 0

    async def fetch_signals(self, **scope):
        assert scope["workspace_id"] == WORKSPACE_ID
        assert scope["platform"] == "google_search"
        assert scope["region"] == "TW"
        assert scope["language"] == "zh-TW"
        self.calls += 1
        return self.signals


def ingestion_signal(*, keyword: str, score: float) -> ProviderKeywordSignal:
    return ProviderKeywordSignal(
        keyword=keyword,
        platform="google_search",
        region="TW",
        language="zh-TW",
        source_name="P5-C2 deterministic integration",
        source_type="synthetic",
        score=score,
        rank=2,
        momentum="rising",
        evidence_note="Deterministic test-only evidence",
        observed_at=NOW,
        expires_at=NOW + timedelta(hours=2),
    )


async def ingestion_rows() -> tuple[tuple, ...]:
    async with Session() as db:
        result = await db.execute(
            text(
                """
                SELECT id::text,workspace_id::text,keyword,
                       normalized_keyword,score
                FROM keyword_trend_signals
                WHERE source_name = 'P5-C2 deterministic integration'
                ORDER BY workspace_id,id
                """
            )
        )
        return tuple(tuple(row) for row in result)


@pytest.mark.asyncio
async def test_p5_c2_real_postgresql_ingestion_upsert_contract() -> None:
    await setup()
    try:
        provider = DeterministicPostgresProvider([
            ingestion_signal(keyword=" AI   行銷 ", score=70),
            ingestion_signal(keyword="ai 行銷", score=90),
        ])
        async with Session() as db:
            first = await refresh_keyword_trend_signals(
                db,
                WORKSPACE_ID,
                platform="google_search",
                region="TW",
                language="zh-TW",
                providers=(provider,),
                now=NOW,
            )
            await db.commit()

        assert first.inserted == 1
        assert first.updated == 0
        assert first.providers_succeeded == 1
        assert first.providers_failed == 0
        assert provider.calls == 1

        rows = await ingestion_rows()
        assert len(rows) == 1
        first_id, workspace_id, keyword, normalized, score = rows[0]
        assert workspace_id == str(WORKSPACE_ID)
        assert keyword == "ai 行銷"
        assert normalized == "ai 行銷"
        assert score == calculate_trend_score(
            90,
            rank=2,
            momentum="rising",
        )

        provider.signals = [
            ingestion_signal(keyword="AI 行銷", score=95),
        ]
        async with Session() as db:
            second = await refresh_keyword_trend_signals(
                db,
                WORKSPACE_ID,
                platform="google_search",
                region="TW",
                language="zh-TW",
                providers=(provider,),
                now=NOW + timedelta(minutes=5),
            )
            await db.commit()

        assert second.inserted == 0
        assert second.updated == 1
        assert provider.calls == 2

        updated_rows = await ingestion_rows()
        assert len(updated_rows) == 1
        assert updated_rows[0][0] == first_id
        assert updated_rows[0][1] == str(WORKSPACE_ID)
        assert updated_rows[0][4] == calculate_trend_score(
            95,
            rank=2,
            momentum="rising",
        )
        assert all(row[1] != str(OTHER_WORKSPACE_ID) for row in updated_rows)
    finally:
        await cleanup()
        await engine.dispose()


async def setup_collective_rows() -> None:
    await cleanup()
    async with Session.begin() as db:
        for index, workspace_id in enumerate(
            COLLECTIVE_WORKSPACE_IDS,
            start=1,
        ):
            await db.execute(
                text(
                    """
                    INSERT INTO workspaces (
                        id,name,slug,created_at,
                        collective_intelligence_enabled
                    ) VALUES (
                        :id,:name,:slug,:created_at,:enabled
                    )
                    """
                ),
                {
                    "id": workspace_id,
                    "name": f"{RUN_TOKEN}-collective-{index}",
                    "slug": f"{RUN_TOKEN}-collective-{index}",
                    "created_at": NOW,
                    "enabled": index != 4,
                },
            )

        rows = (
            (COLLECTIVE_WORKSPACE_IDS[0], "共同趨勢", 80.0, "source-a"),
            (COLLECTIVE_WORKSPACE_IDS[0], "共同趨勢", 95.0, "source-b"),
            (COLLECTIVE_WORKSPACE_IDS[1], "共同趨勢", 70.0, "source-c"),
            (COLLECTIVE_WORKSPACE_IDS[2], "共同趨勢", 60.0, "source-d"),
            (COLLECTIVE_WORKSPACE_IDS[3], "共同趨勢", 100.0, "opted-out"),
            (COLLECTIVE_WORKSPACE_IDS[0], "低門檻私有詞", 99.0, "private-a"),
            (COLLECTIVE_WORKSPACE_IDS[1], "低門檻私有詞", 99.0, "private-b"),
        )
        for index, (workspace_id, keyword, score, source) in enumerate(rows):
            await db.execute(
                text(
                    """
                    INSERT INTO keyword_trend_signals (
                        id,workspace_id,keyword,normalized_keyword,
                        platform,region,language,source_name,source_type,
                        score,rank,momentum,evidence_note,observed_at,
                        expires_at,created_at
                    ) VALUES (
                        :id,:workspace_id,:keyword,:normalized_keyword,
                        'google_search','TW','zh-TW',:source,'synthetic',
                        :score,1,'rising','test-only evidence',:observed_at,
                        :expires_at,:created_at
                    )
                    """
                ),
                {
                    "id": integration_uuid(f"p5-c3-signal-{index}"),
                    "workspace_id": workspace_id,
                    "keyword": keyword,
                    "normalized_keyword": keyword,
                    "source": source,
                    "score": score,
                    "observed_at": NOW - timedelta(minutes=index + 1),
                    "expires_at": NOW + timedelta(hours=2),
                    "created_at": NOW - timedelta(minutes=index + 1),
                },
            )


@pytest.mark.asyncio
async def test_p5_c3_privacy_preserving_collective_contract() -> None:
    await setup_collective_rows()
    try:
        requester = COLLECTIVE_WORKSPACE_IDS[0]
        async with Session() as db:
            response = await list_collective_keyword_trends(
                db,
                requester,
                CollectiveKeywordQueryParameters(
                    platform="google_search",
                    region="TW",
                    language="zh-TW",
                    window_hours=24,
                ),
                now=NOW,
            )

        assert response.collective_intelligence_enabled is True
        assert [item.keyword for item in response.items] == ["共同趨勢"]
        item = response.items[0]
        assert item.contributor_cohort == "3-9"
        assert item.source_diversity == "multiple"
        assert item.score == pytest.approx(75.0)
        assert item.signal_scope == "collective"
        payload = response.model_dump_json()
        assert "低門檻私有詞" not in payload
        assert "opted-out" not in payload
        assert all(
            str(value) not in payload
            for value in COLLECTIVE_WORKSPACE_IDS[1:]
        )

        async with Session.begin() as db:
            await db.execute(
                text(
                    """
                    UPDATE workspaces
                    SET collective_intelligence_enabled = false
                    WHERE id = :workspace_id
                    """
                ),
                {"workspace_id": requester},
            )
        async with Session() as db:
            opted_out = await list_collective_keyword_trends(
                db,
                requester,
                CollectiveKeywordQueryParameters(),
                now=NOW,
            )
        assert opted_out.collective_intelligence_enabled is False
        assert opted_out.items == []
    finally:
        await cleanup()
        await engine.dispose()


@pytest.mark.asyncio
async def test_p5_c4_real_postgresql_bounded_context_contract() -> None:
    await setup_collective_rows()
    try:
        requester = COLLECTIVE_WORKSPACE_IDS[0]
        async with Session() as db:
            response = await assemble_intelligence_context(
                db,
                requester,
                IntelligenceContextQueryParameters(
                    platform="google_search",
                    region="TW",
                    language="zh-TW",
                    window_hours=24,
                ),
                now=NOW,
            )

        scopes = {item.signal_scope for item in response.items}
        assert scopes == {"workspace", "collective"}
        assert response.item_count == len(response.items)
        assert response.item_count <= 20
        assert response.context_bytes <= 8192
        local_keywords = {
            item.keyword
            for item in response.items
            if item.signal_scope == "workspace"
        }
        collective_keywords = {
            item.keyword
            for item in response.items
            if item.signal_scope == "collective"
        }
        assert "低門檻私有詞" in local_keywords
        assert collective_keywords == {"共同趨勢"}

        payload = response.model_dump_json()
        assert "opted-out" not in payload
        assert "source-a" not in payload
        assert "test-only evidence" not in payload
        assert all(
            str(value) not in payload
            for value in COLLECTIVE_WORKSPACE_IDS[1:]
        )

        async with Session.begin() as db:
            await db.execute(
                text(
                    """
                    UPDATE workspaces
                    SET collective_intelligence_enabled = false
                    WHERE id = :workspace_id
                    """
                ),
                {"workspace_id": requester},
            )

        async with Session() as db:
            opted_out = await assemble_intelligence_context(
                db,
                requester,
                IntelligenceContextQueryParameters(),
                now=NOW,
            )

        assert opted_out.collective_intelligence_enabled is False
        assert opted_out.items
        assert all(
            item.signal_scope == "workspace"
            for item in opted_out.items
        )
    finally:
        await cleanup()
        await engine.dispose()


@pytest.mark.asyncio
async def test_p5_c5_real_postgresql_answer_context_contract() -> None:
    from app.services.ai_answer_orchestration import prepare_ai_answer

    await setup_collective_rows()
    try:
        requester = COLLECTIVE_WORKSPACE_IDS[0]
        async with Session() as db:
            prepared = await prepare_ai_answer(
                db,
                requester,
                "synthetic brand prompt",
                IntelligenceContextQueryParameters(
                    platform="google_search",
                    region="TW",
                    language="zh-TW",
                    window_hours=24,
                ),
                now=NOW,
            )
        assert prepared.local_item_count >= 1
        assert prepared.collective_item_count == 1
        assert prepared.context_item_count <= 20
        assert len(prepared.prompt.encode("utf-8")) <= 24_576
        assert "低門檻私有詞" in prepared.prompt
        assert "共同趨勢" in prepared.prompt
        assert "source-a" not in prepared.prompt
        assert "test-only evidence" not in prepared.prompt
        assert all(
            str(value) not in prepared.prompt
            for value in COLLECTIVE_WORKSPACE_IDS[1:]
        )
    finally:
        await cleanup()
        await engine.dispose()


@pytest.mark.asyncio
async def test_p5_c6_real_postgresql_quality_feedback_contract() -> None:
    from sqlalchemy.exc import IntegrityError

    workspace_id = integration_uuid("p5-c6-quality-workspace")
    other_workspace_id = integration_uuid("p5-c6-quality-other-workspace")
    user_id = integration_uuid("p5-c6-quality-user")
    brand_id = integration_uuid("p5-c6-quality-brand")
    generation_id = integration_uuid("p5-c6-quality-generation")
    feedback_id = integration_uuid("p5-c6-quality-feedback")

    async def remove_rows() -> None:
        async with Session.begin() as db:
            await db.execute(
                text("DELETE FROM workspaces WHERE id = ANY(:ids)"),
                {"ids": [workspace_id, other_workspace_id]},
            )
            await db.execute(
                text("DELETE FROM users WHERE id = :id"),
                {"id": user_id},
            )

    await remove_rows()
    try:
        async with Session.begin() as db:
            await db.execute(text(
                "INSERT INTO users (id,email,is_active,created_at) "
                "VALUES (:id,:email,true,now())"
            ), {"id": user_id, "email": RUN_TOKEN + "-quality@example.invalid"})
            for value, suffix in (
                (workspace_id, "quality"),
                (other_workspace_id, "quality-other"),
            ):
                await db.execute(text(
                    "INSERT INTO workspaces (id,name,slug,created_at) "
                    "VALUES (:id,:name,:slug,now())"
                ), {
                    "id": value,
                    "name": f"{RUN_TOKEN}-{suffix}",
                    "slug": f"{RUN_TOKEN}-{suffix}",
                })
            await db.execute(text(
                "INSERT INTO brands (id,workspace_id,name,language,created_at) "
                "VALUES (:id,:workspace_id,:name,'en',now())"
            ), {"id": brand_id, "workspace_id": workspace_id, "name": RUN_TOKEN})
            await db.execute(text("""
                INSERT INTO content_generations (
                    id,workspace_id,brand_id,user_id,platform,topic,status,
                    quality_score,quality_evaluator,quality_disclosure,
                    created_at,updated_at
                ) VALUES (
                    :id,:workspace_id,:brand_id,:user_id,'facebook','quality',
                    'completed',87,'deterministic-quality-v1',NULL,now(),now()
                )
            """), {
                "id": generation_id,
                "workspace_id": workspace_id,
                "brand_id": brand_id,
                "user_id": user_id,
            })
            await db.execute(text("""
                INSERT INTO ai_answer_feedback (
                    id,workspace_id,generation_id,user_id,rating,reason,
                    comment,created_at,updated_at
                ) VALUES (
                    :id,:workspace_id,:generation_id,:user_id,5,'helpful',
                    'synthetic bounded feedback',now(),now()
                )
            """), {
                "id": feedback_id,
                "workspace_id": workspace_id,
                "generation_id": generation_id,
                "user_id": user_id,
            })

        async with Session() as db:
            row = (await db.execute(text("""
                SELECT g.quality_score,g.quality_evaluator,
                       f.rating,f.reason::text,f.comment
                FROM content_generations g
                JOIN ai_answer_feedback f ON f.generation_id = g.id
                WHERE g.workspace_id = :workspace_id
                  AND f.workspace_id = :workspace_id
            """), {"workspace_id": workspace_id})).one()
            assert tuple(row) == (
                87, "deterministic-quality-v1", 5, "helpful",
                "synthetic bounded feedback",
            )
            leaked = await db.scalar(text("""
                SELECT count(*) FROM ai_answer_feedback
                WHERE workspace_id = :other_workspace_id
                  AND generation_id = :generation_id
            """), {
                "other_workspace_id": other_workspace_id,
                "generation_id": generation_id,
            })
            assert leaked == 0

        with pytest.raises(IntegrityError):
            async with Session.begin() as db:
                await db.execute(text("""
                    INSERT INTO ai_answer_feedback (
                        id,workspace_id,generation_id,user_id,rating,reason,
                        created_at,updated_at
                    ) VALUES (
                        :id,:workspace_id,:generation_id,:user_id,6,'helpful',
                        now(),now()
                    )
                """), {
                    "id": integration_uuid("p5-c6-invalid-feedback"),
                    "workspace_id": other_workspace_id,
                    "generation_id": generation_id,
                    "user_id": user_id,
                })
    finally:
        await remove_rows()
        await engine.dispose()


@pytest.mark.asyncio
async def test_p5_c7_real_postgresql_quality_policy_governance_contract() -> None:
    from sqlalchemy.exc import IntegrityError

    workspace_id = integration_uuid("p5-c7-policy-workspace")
    other_workspace_id = integration_uuid("p5-c7-policy-other-workspace")
    user_id = integration_uuid("p5-c7-policy-user")
    brand_id = integration_uuid("p5-c7-policy-brand")
    recommendation_id = integration_uuid("p5-c7-policy-recommendation")

    async def remove_rows() -> None:
        async with Session.begin() as db:
            await db.execute(
                text("DELETE FROM workspaces WHERE id = ANY(:ids)"),
                {"ids": [workspace_id, other_workspace_id]},
            )
            await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})

    await remove_rows()
    try:
        async with Session.begin() as db:
            await db.execute(
                text(
                    "INSERT INTO users (id,email,is_active,created_at) "
                    "VALUES (:id,:email,true,now())"
                ),
                {"id": user_id, "email": RUN_TOKEN + "-policy@example.invalid"},
            )
            for value, suffix in (
                (workspace_id, "policy"),
                (other_workspace_id, "policy-other"),
            ):
                await db.execute(
                    text(
                        "INSERT INTO workspaces (id,name,slug,created_at) "
                        "VALUES (:id,:name,:slug,now())"
                    ),
                    {
                        "id": value,
                        "name": f"{RUN_TOKEN}-{suffix}",
                        "slug": f"{RUN_TOKEN}-{suffix}",
                    },
                )
            await db.execute(
                text(
                    "INSERT INTO brands (id,workspace_id,name,language,created_at) "
                    "VALUES (:id,:workspace_id,:name,'en',now())"
                ),
                {"id": brand_id, "workspace_id": workspace_id, "name": RUN_TOKEN},
            )
            await db.execute(
                text("""
                    INSERT INTO ai_quality_policy_recommendations (
                        id,workspace_id,brand_id,version,status,
                        minimum_quality_score,minimum_cohort_size,
                        maximum_workspace_contribution,observation_count,
                        distinct_workspace_count,average_quality_score,
                        average_rating,confidence_score,recommendation_reason,
                        provenance,created_at,updated_at
                    ) VALUES (
                        :id,:workspace_id,:brand_id,1,'candidate',60,12,6,18,3,
                        70.00,3.50,85,'aggregate_quality_within_target',
                        'clipped_aggregate_quality_feedback',now(),now()
                    )
                """),
                {
                    "id": recommendation_id,
                    "workspace_id": workspace_id,
                    "brand_id": brand_id,
                },
            )

        async with Session() as db:
            row = (
                await db.execute(
                    text("""
                        SELECT version,status::text,minimum_quality_score,
                               observation_count,distinct_workspace_count,
                               provenance
                        FROM ai_quality_policy_recommendations
                        WHERE id=:id AND workspace_id=:workspace_id
                    """),
                    {"id": recommendation_id, "workspace_id": workspace_id},
                )
            ).one()
            assert tuple(row) == (
                1,
                "candidate",
                60,
                18,
                3,
                "clipped_aggregate_quality_feedback",
            )
            leaked = await db.scalar(
                text("""
                    SELECT count(*) FROM ai_quality_policy_recommendations
                    WHERE workspace_id=:workspace_id AND id=:id
                """),
                {"workspace_id": other_workspace_id, "id": recommendation_id},
            )
            assert leaked == 0

        async with Session.begin() as db:
            await db.execute(
                text("""
                    UPDATE ai_quality_policy_recommendations
                    SET status='approved',approved_by_user_id=:user_id,
                        approved_at=now(),updated_at=now()
                    WHERE id=:id AND workspace_id=:workspace_id
                """),
                {
                    "id": recommendation_id,
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                },
            )
            await db.execute(
                text("""
                    INSERT INTO ai_quality_policy_decision_audits (
                        id,recommendation_id,workspace_id,actor_user_id,
                        previous_status,new_status,reason,created_at
                    ) VALUES (
                        :id,:recommendation_id,:workspace_id,:actor_user_id,
                        'candidate','approved','synthetic human approval',now()
                    )
                """),
                {
                    "id": integration_uuid("p5-c7-policy-audit"),
                    "recommendation_id": recommendation_id,
                    "workspace_id": workspace_id,
                    "actor_user_id": user_id,
                },
            )

        async with Session() as db:
            decision = (
                await db.execute(
                    text("""
                        SELECT r.status::text,a.previous_status::text,
                               a.new_status::text,a.reason
                        FROM ai_quality_policy_recommendations r
                        JOIN ai_quality_policy_decision_audits a
                          ON a.recommendation_id=r.id
                        WHERE r.id=:id AND r.workspace_id=:workspace_id
                          AND a.workspace_id=:workspace_id
                    """),
                    {"id": recommendation_id, "workspace_id": workspace_id},
                )
            ).one()
            assert tuple(decision) == (
                "approved",
                "candidate",
                "approved",
                "synthetic human approval",
            )

        with pytest.raises(IntegrityError):
            async with Session.begin() as db:
                await db.execute(
                    text("""
                        INSERT INTO ai_quality_policy_recommendations (
                            id,workspace_id,brand_id,version,status,
                            minimum_quality_score,minimum_cohort_size,
                            maximum_workspace_contribution,observation_count,
                            distinct_workspace_count,average_quality_score,
                            average_rating,confidence_score,recommendation_reason,
                            provenance,created_at,updated_at
                        ) VALUES (
                            :id,:workspace_id,:brand_id,2,'candidate',101,12,6,
                            18,3,70.00,3.50,85,'invalid_test_candidate',
                            'clipped_aggregate_quality_feedback',now(),now()
                        )
                    """),
                    {
                        "id": integration_uuid("p5-c7-invalid-policy"),
                        "workspace_id": workspace_id,
                        "brand_id": brand_id,
                    },
                )
    finally:
        await remove_rows()
        await engine.dispose()
