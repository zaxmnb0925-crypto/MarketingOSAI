import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import keyword_intelligence as api
from app.models.keyword_intelligence import KeywordTrendSignal
from app.schemas.keyword_intelligence import KeywordTrendQueryParameters
from app.services import keyword_intelligence as service


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeResult:
    def __init__(self, values):
        self.values = values

    def scalars(self):
        return FakeScalars(self.values)


class FakeDB:
    def __init__(self, values):
        self.values = values
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.values)


def signal(*, expires_at):
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        keyword="AI 行銷",
        platform="google_search",
        region="TW",
        language="zh-TW",
        source_name="Synthetic contract fixture",
        source_type="synthetic",
        score=88.5,
        rank=2,
        momentum="rising",
        evidence_note="Test-only evidence",
        observed_at=now - timedelta(hours=1),
        expires_at=expires_at,
    )


def test_model_requires_workspace_and_provenance_fields():
    columns = KeywordTrendSignal.__table__.columns
    required = {
        "workspace_id",
        "keyword",
        "normalized_keyword",
        "platform",
        "region",
        "language",
        "source_name",
        "source_type",
        "observed_at",
        "expires_at",
    }
    assert required.issubset(columns.keys())
    assert all(not columns[name].nullable for name in required)


def test_provider_is_protocol_only_with_no_network_implementation():
    source = inspect.getsource(service)
    assert "class KeywordSignalProvider(Protocol)" in source
    assert "httpx" not in source
    assert "requests" not in source
    assert "aiohttp" not in source


def test_keyword_normalization_is_stable():
    assert service.normalize_keyword("  AI   行銷  ") == "ai 行銷"


def test_freshness_is_derived_from_expiry():
    now = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    fresh = service.serialize_signal(
        signal(expires_at=now + timedelta(minutes=1)),
        now=now,
    )
    stale = service.serialize_signal(
        signal(expires_at=now),
        now=now,
    )
    assert fresh.stale is False
    assert stale.stale is True


@pytest.mark.asyncio
async def test_query_is_workspace_scoped_and_stale_closed_by_default():
    now = datetime(2026, 8, 28, 12, tzinfo=timezone.utc)
    db = FakeDB([])
    workspace_id = uuid4()
    response = await service.list_keyword_trend_signals(
        db,
        workspace_id,
        KeywordTrendQueryParameters(),
        now=now,
    )
    sql = str(db.statement)
    assert "keyword_trend_signals.workspace_id" in sql
    assert "keyword_trend_signals.expires_at" in sql
    assert response.workspace_id == workspace_id
    assert response.stale_results_included is False


def test_api_is_authenticated_read_only_and_workspace_guarded():
    source = inspect.getsource(api.read_keyword_trend_signals)
    assert "get_current_user" in source
    assert "require_workspace_membership" in source
    assert "list_keyword_trend_signals" in source
    assert not any(
        route.methods.intersection({"POST", "PUT", "PATCH", "DELETE"})
        for route in api.router.routes
    )


def test_openapi_discloses_read_route_only():
    from app.main import app

    path = "/api/workspaces/{workspace_id}/keyword-signals"
    operations = app.openapi()["paths"][path]
    assert set(operations) == {"get"}


def test_migration_is_fail_closed_and_has_no_seed_or_network_data():
    from pathlib import Path

    migration = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "9f31a7c2d4e6_add_keyword_intelligence_foundation.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "f0289623eb1e"' in migration
    assert "expires_at > observed_at" in migration
    assert "score >= 0 AND score <= 100" in migration
    assert "INSERT INTO" not in migration
    assert "http" not in migration
