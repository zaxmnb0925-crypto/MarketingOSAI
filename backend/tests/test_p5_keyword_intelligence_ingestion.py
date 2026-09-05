from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.services import keyword_intelligence as service


NOW = datetime(2026, 8, 29, 3, tzinfo=timezone.utc)


def provider_signal(keyword=" AI   行銷 ", *, score=80, rank=2):
    return service.ProviderKeywordSignal(
        keyword=keyword,
        platform="google_search",
        region="TW",
        language="zh-TW",
        source_name="deterministic_fake",
        source_type="synthetic",
        score=score,
        rank=rank,
        momentum="rising",
        evidence_note="test-only evidence",
        observed_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


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
    def __init__(self, existing=()):
        self.existing = list(existing)
        self.added = []
        self.flushes = 0

    async def execute(self, statement):
        self.statement = statement
        return FakeResult(self.existing)

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        self.flushes += 1


class DeterministicFakeProvider:
    provider_name = "deterministic_fake"

    def __init__(self, signals=(), failures=0, permanent=False):
        self.signals = list(signals)
        self.failures = failures
        self.permanent = permanent
        self.calls = 0

    async def fetch_signals(self, **scope):
        self.calls += 1
        if self.permanent:
            raise service.PermanentKeywordProviderError("synthetic secret")
        if self.calls <= self.failures:
            raise service.RetryableKeywordProviderError("synthetic secret")
        return self.signals


@pytest.mark.asyncio
async def test_refresh_normalizes_deduplicates_scores_and_inserts():
    db = FakeDB()
    provider = DeterministicFakeProvider([
        provider_signal(score=70),
        provider_signal(keyword="ai 行銷", score=90),
    ])
    response = await service.refresh_keyword_trend_signals(
        db,
        uuid4(),
        platform="google_search",
        region="TW",
        language="zh-TW",
        providers=(provider,),
        now=NOW,
    )
    assert response.inserted == 1
    assert response.updated == 0
    assert response.providers_succeeded == 1
    assert len(db.added) == 1
    assert db.added[0].normalized_keyword == "ai 行銷"
    assert db.added[0].score == service.calculate_trend_score(
        90, rank=2, momentum="rising"
    )
    assert db.flushes == 1


@pytest.mark.asyncio
async def test_retry_is_bounded_and_provider_failure_is_isolated():
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    failing = DeterministicFakeProvider(failures=3)
    succeeding = DeterministicFakeProvider([provider_signal()])
    succeeding.provider_name = "second_fake"
    db = FakeDB()
    response = await service.refresh_keyword_trend_signals(
        db,
        uuid4(),
        platform="google_search",
        region="TW",
        language="zh-TW",
        providers=(failing, succeeding),
        policy=service.KeywordRefreshPolicy(
            max_attempts=3,
            retry_delay_seconds=0,
        ),
        now=NOW,
        sleep=fake_sleep,
    )
    assert failing.calls == 3
    assert succeeding.calls == 1
    assert sleeps == [0, 0]
    assert response.providers_failed == 1
    assert response.providers_succeeded == 1
    assert response.provider_results[0].failure_class == "retry_exhausted"
    assert "secret" not in response.model_dump_json()


@pytest.mark.asyncio
async def test_existing_signal_is_updated_without_cross_workspace_query():
    existing = service.KeywordTrendSignal(
        workspace_id=uuid4(),
        keyword="old",
        normalized_keyword="ai 行銷",
        platform="google_search",
        region="TW",
        language="zh-TW",
        source_name="deterministic_fake",
        source_type="synthetic",
        score=1,
        observed_at=NOW - timedelta(hours=2),
        expires_at=NOW - timedelta(hours=1),
    )
    workspace_id = existing.workspace_id
    db = FakeDB([existing])
    response = await service.refresh_keyword_trend_signals(
        db,
        workspace_id,
        platform="google_search",
        region="TW",
        language="zh-TW",
        providers=(DeterministicFakeProvider([provider_signal()]),),
        now=NOW,
    )
    assert response.inserted == 0
    assert response.updated == 1
    assert db.added == []
    assert "keyword_trend_signals.workspace_id" in str(db.statement)
    assert existing.keyword == "AI   行銷"


def test_invalid_provider_scope_and_policy_fail_closed():
    wrong_scope = provider_signal()
    wrong_scope = service.ProviderKeywordSignal(
        **{**wrong_scope.__dict__, "region": "US"}
    )
    with pytest.raises(service.KeywordSignalValidationError):
        service._deduplicate_signals(
            [wrong_scope],
            platform="google_search",
            region="TW",
            language="zh-TW",
        )
    with pytest.raises(ValueError):
        service.KeywordRefreshPolicy(max_attempts=4)


@pytest.mark.asyncio
async def test_direct_schedule_boundary_rejects_invalid_scope():
    with pytest.raises(ValueError):
        await service.refresh_keyword_trend_signals(
            FakeDB(),
            uuid4(),
            platform="",
            region="TW",
            language="zh-TW",
            providers=(DeterministicFakeProvider(),),
            now=NOW,
        )


def test_production_provider_wiring_is_fail_closed_and_network_free():
    from app.api import keyword_intelligence as api

    assert api.get_keyword_signal_providers() == ()
    source = __import__("inspect").getsource(service)
    assert "httpx" not in source
    assert "requests" not in source
    assert "aiohttp" not in source
