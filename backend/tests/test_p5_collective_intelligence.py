import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import keyword_intelligence as api
from app.models.workspace import Workspace
from app.schemas.keyword_intelligence import (
    CollectiveKeywordQueryParameters,
)
from app.services import keyword_intelligence as service


NOW = datetime(2026, 8, 29, 6, tzinfo=timezone.utc)


class FakeResult:
    def __init__(self, *, scalar=None, rows=()):
        self.scalar = scalar
        self.rows = list(rows)

    def scalar_one_or_none(self):
        return self.scalar

    def all(self):
        return self.rows


class SequencedDB:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []
        self.flushes = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)

    async def flush(self):
        self.flushes += 1


def aggregate_row(*, score=81.25, workspaces=3):
    return SimpleNamespace(
        keyword="ai 行銷",
        platform="google_search",
        region="TW",
        language="zh-TW",
        aggregate_score=score,
        workspace_count=workspaces,
        source_count=2,
        observed_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=1),
    )


def test_workspace_has_explicit_collective_preference():
    column = Workspace.__table__.columns[
        "collective_intelligence_enabled"
    ]
    assert column.nullable is False
    assert column.server_default is not None


def test_collective_policy_is_privacy_bounded():
    policy = service.CollectiveIntelligencePolicy()
    assert policy.minimum_contributing_workspaces == 3
    assert policy.maximum_contributions_per_workspace == 1
    assert policy.window_hours == 24
    with pytest.raises(ValueError):
        service.CollectiveIntelligencePolicy(
            minimum_contributing_workspaces=2
        )
    with pytest.raises(ValueError):
        service.CollectiveIntelligencePolicy(
            maximum_contributions_per_workspace=2
        )
    with pytest.raises(ValueError):
        CollectiveKeywordQueryParameters(minimum_workspaces=3)


@pytest.mark.asyncio
async def test_opted_out_workspace_receives_no_collective_results():
    db = SequencedDB([FakeResult(scalar=False)])
    workspace_id = uuid4()
    response = await service.list_collective_keyword_trends(
        db,
        workspace_id,
        CollectiveKeywordQueryParameters(),
        now=NOW,
    )
    assert response.workspace_id == workspace_id
    assert response.collective_intelligence_enabled is False
    assert response.items == []
    assert len(db.statements) == 1


@pytest.mark.asyncio
async def test_collective_query_clips_and_thresholds_contributions():
    db = SequencedDB([
        FakeResult(scalar=True),
        FakeResult(rows=[aggregate_row()]),
    ])
    response = await service.list_collective_keyword_trends(
        db,
        uuid4(),
        CollectiveKeywordQueryParameters(
            platform="google_search",
            region="TW",
            language="zh-TW",
            query=" AI  行銷 ",
        ),
        now=NOW,
    )
    sql = str(db.statements[1])
    assert "row_number() OVER" in sql
    assert "count(distinct" in sql.lower()
    assert "HAVING" in sql
    assert "collective_intelligence_enabled" in sql
    assert "expires_at" in sql
    assert "observed_at" in sql
    assert len(response.items) == 1
    item = response.items[0]
    assert item.keyword == "ai 行銷"
    assert item.contributor_cohort == "3-9"
    assert item.source_diversity == "multiple"
    assert item.signal_scope == "collective"
    assert item.provenance == "privacy_preserving_aggregate"
    assert item.momentum == "rising"


def test_collective_response_cannot_expose_contributor_identity():
    from app.schemas.keyword_intelligence import (
        CollectiveKeywordSignalResponse,
    )

    fields = set(CollectiveKeywordSignalResponse.model_fields)
    assert "workspace_id" not in fields
    assert "contributor_id" not in fields
    assert "source_name" not in fields
    assert "evidence_note" not in fields
    assert "contributing_workspaces" not in fields
    assert "source_count" not in fields
    assert "raw_prompt" not in fields
    assert "raw_content" not in fields


@pytest.mark.asyncio
async def test_workspace_can_disable_collective_participation():
    workspace = SimpleNamespace(
        id=uuid4(),
        collective_intelligence_enabled=True,
    )
    db = SequencedDB([FakeResult(scalar=workspace)])
    response = await service.set_collective_intelligence_preference(
        db,
        workspace.id,
        enabled=False,
    )
    assert workspace.collective_intelligence_enabled is False
    assert response.enabled is False
    assert db.flushes == 1


def test_collective_routes_are_authenticated_and_guarded():
    read_source = inspect.getsource(
        api.read_collective_keyword_trends
    )
    update_source = inspect.getsource(
        api.update_collective_intelligence_preference
    )
    assert "get_current_user" in read_source
    assert "require_workspace_membership" in read_source
    assert "require_workspace_write" in update_source
    routes = {route.path: route.methods for route in api.router.routes}
    base = "/api/workspaces/{workspace_id}/keyword-signals"
    assert routes[f"{base}/collective"] == {"GET"}
    assert routes[f"{base}/collective-preference"] == {"PATCH"}


def test_collective_service_has_no_network_or_ai_transport():
    source = inspect.getsource(service.list_collective_keyword_trends)
    assert "httpx" not in source
    assert "requests" not in source
    assert "aiohttp" not in source
    assert "openai" not in source.lower()


def test_collective_migration_is_additive_and_seed_free():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "4a7d9c2e6f10_add_collective_intelligence_preference.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "9f31a7c2d4e6"' in migration
    assert "collective_intelligence_enabled" in migration
    assert "server_default=sa.true()" in migration
    assert "INSERT INTO" not in migration
    assert "http" not in migration
