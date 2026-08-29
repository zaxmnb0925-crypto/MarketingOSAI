import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_intelligence import KeywordTrendSignal
from app.models.workspace import Workspace
from app.schemas.keyword_intelligence import (
    CollectiveIntelligencePreferenceResponse,
    CollectiveKeywordQueryParameters,
    CollectiveKeywordSignalListResponse,
    CollectiveKeywordSignalResponse,
    KeywordTrendQueryParameters,
    KeywordProviderRefreshResult,
    KeywordSignalRefreshResponse,
    KeywordTrendSignalListResponse,
    KeywordTrendSignalResponse,
)


@dataclass(frozen=True)
class ProviderKeywordSignal:
    keyword: str
    platform: str
    region: str
    language: str
    source_name: str
    source_type: str
    score: float
    rank: int | None
    momentum: str | None
    evidence_note: str | None
    observed_at: datetime
    expires_at: datetime


class KeywordSignalProvider(Protocol):
    """Provider contract; implementations own transport and credentials."""

    provider_name: str

    async def fetch_signals(
        self,
        *,
        workspace_id: UUID,
        platform: str,
        region: str,
        language: str,
    ) -> list[ProviderKeywordSignal]: ...


class RetryableKeywordProviderError(RuntimeError):
    """A provider failed before returning a usable response."""


class PermanentKeywordProviderError(RuntimeError):
    """A provider rejected the request and must not be retried."""


class KeywordSignalValidationError(ValueError):
    pass


@dataclass(frozen=True)
class KeywordRefreshPolicy:
    max_attempts: int = 3
    retry_delay_seconds: float = 0

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if not 0 <= self.retry_delay_seconds <= 5:
            raise ValueError("retry delay must be between 0 and 5 seconds")


Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class CollectiveIntelligencePolicy:
    minimum_contributing_workspaces: int = 3
    maximum_contributions_per_workspace: int = 1
    window_hours: int = 24

    def __post_init__(self) -> None:
        if not 3 <= self.minimum_contributing_workspaces <= 100:
            raise ValueError("collective workspace threshold is invalid")
        if self.maximum_contributions_per_workspace != 1:
            raise ValueError("workspace contribution clipping must be one")
        if not 1 <= self.window_hours <= 168:
            raise ValueError("collective time window is invalid")


def calculate_trend_score(
    provider_score: float,
    *,
    rank: int | None,
    momentum: str | None,
) -> float:
    """Create one stable 0-100 score from bounded provider evidence."""
    if not 0 <= provider_score <= 100:
        raise KeywordSignalValidationError("provider score is out of range")
    if rank is not None and rank < 1:
        raise KeywordSignalValidationError("provider rank must be positive")

    rank_bonus = 0.0 if rank is None else max(0.0, 12.0 - min(rank, 12))
    momentum_adjustment = {
        "rising": 5.0,
        "stable": 0.0,
        "falling": -5.0,
    }.get(momentum, 0.0)
    score = provider_score * 0.84 + rank_bonus + momentum_adjustment
    return round(min(100.0, max(0.0, score)), 4)


def _validate_provider_signal(
    signal: ProviderKeywordSignal,
    *,
    platform: str,
    region: str,
    language: str,
) -> str:
    normalized = normalize_keyword(signal.keyword)
    if not normalized or len(signal.keyword) > 200 or len(normalized) > 200:
        raise KeywordSignalValidationError("provider keyword is invalid")
    if (
        signal.platform != platform
        or signal.region != region
        or signal.language != language
    ):
        raise KeywordSignalValidationError("provider scope mismatch")
    if (
        not signal.source_name.strip()
        or len(signal.source_name) > 120
        or not signal.source_type.strip()
        or len(signal.source_type) > 40
    ):
        raise KeywordSignalValidationError("provider provenance is missing")
    if signal.evidence_note is not None and len(signal.evidence_note) > 2000:
        raise KeywordSignalValidationError("provider evidence is too long")
    if signal.observed_at.tzinfo is None or signal.expires_at.tzinfo is None:
        raise KeywordSignalValidationError("provider timestamps need timezone")
    if signal.expires_at <= signal.observed_at:
        raise KeywordSignalValidationError("provider expiry is invalid")
    calculate_trend_score(
        signal.score,
        rank=signal.rank,
        momentum=signal.momentum,
    )
    return normalized


def _deduplicate_signals(
    signals: Sequence[ProviderKeywordSignal],
    *,
    platform: str,
    region: str,
    language: str,
) -> list[tuple[ProviderKeywordSignal, str, float]]:
    selected: dict[
        tuple[str, str, str, str, str],
        tuple[ProviderKeywordSignal, str, float],
    ] = {}
    for signal in signals:
        normalized = _validate_provider_signal(
            signal,
            platform=platform,
            region=region,
            language=language,
        )
        score = calculate_trend_score(
            signal.score,
            rank=signal.rank,
            momentum=signal.momentum,
        )
        key = (
            normalized,
            signal.platform,
            signal.region,
            signal.language,
            signal.source_name.strip(),
        )
        current = selected.get(key)
        if current is None or (score, signal.observed_at) > (
            current[2],
            current[0].observed_at,
        ):
            selected[key] = (signal, normalized, score)
    return [selected[key] for key in sorted(selected)]


async def _fetch_with_bounded_retry(
    provider: KeywordSignalProvider,
    *,
    workspace_id: UUID,
    platform: str,
    region: str,
    language: str,
    policy: KeywordRefreshPolicy,
    sleep: Sleep,
) -> tuple[list[ProviderKeywordSignal], int]:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await provider.fetch_signals(
                workspace_id=workspace_id,
                platform=platform,
                region=region,
                language=language,
            ), attempt
        except PermanentKeywordProviderError:
            raise
        except RetryableKeywordProviderError:
            if attempt == policy.max_attempts:
                raise
            await sleep(policy.retry_delay_seconds)
        except Exception as exc:
            raise PermanentKeywordProviderError(
                "provider execution failed"
            ) from exc
    raise AssertionError("bounded retry loop exhausted")


async def refresh_keyword_trend_signals(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    platform: str,
    region: str,
    language: str,
    providers: Sequence[KeywordSignalProvider],
    policy: KeywordRefreshPolicy | None = None,
    now: datetime | None = None,
    sleep: Sleep = asyncio.sleep,
) -> KeywordSignalRefreshResponse:
    """Schedule-ready orchestration with provider-level failure isolation."""
    if (
        not platform.strip()
        or len(platform) > 40
        or not region.strip()
        or len(region) > 16
        or not language.strip()
        or len(language) > 20
    ):
        raise ValueError("keyword refresh scope is invalid")
    if not providers:
        raise ValueError("at least one keyword provider is required")
    provider_names = [provider.provider_name.strip() for provider in providers]
    if any(not name for name in provider_names):
        raise ValueError("provider name is required")
    if len(provider_names) != len(set(provider_names)):
        raise ValueError("provider names must be unique")

    effective_policy = policy or KeywordRefreshPolicy()
    refreshed_at = now or utcnow()
    accepted: list[tuple[ProviderKeywordSignal, str, float]] = []
    results: list[KeywordProviderRefreshResult] = []

    for provider, provider_name in zip(providers, provider_names, strict=True):
        attempts = 1
        try:
            fetched, attempts = await _fetch_with_bounded_retry(
                provider,
                workspace_id=workspace_id,
                platform=platform,
                region=region,
                language=language,
                policy=effective_policy,
                sleep=sleep,
            )
            deduplicated = _deduplicate_signals(
                fetched,
                platform=platform,
                region=region,
                language=language,
            )
            accepted.extend(deduplicated)
            results.append(KeywordProviderRefreshResult(
                provider=provider_name,
                status="succeeded",
                attempts=attempts,
                accepted_signals=len(deduplicated),
            ))
        except RetryableKeywordProviderError:
            results.append(KeywordProviderRefreshResult(
                provider=provider_name,
                status="failed",
                attempts=effective_policy.max_attempts,
                accepted_signals=0,
                failure_class="retry_exhausted",
            ))
        except (PermanentKeywordProviderError, KeywordSignalValidationError):
            results.append(KeywordProviderRefreshResult(
                provider=provider_name,
                status="failed",
                attempts=attempts,
                accepted_signals=0,
                failure_class="provider_rejected",
            ))

    statement = select(KeywordTrendSignal).where(
        KeywordTrendSignal.workspace_id == workspace_id,
        KeywordTrendSignal.platform == platform,
        KeywordTrendSignal.region == region,
        KeywordTrendSignal.language == language,
    )
    existing_result = await db.execute(statement)
    existing = {
        (
            item.normalized_keyword,
            item.platform,
            item.region,
            item.language,
            item.source_name,
        ): item
        for item in existing_result.scalars().all()
    }

    inserted = 0
    updated = 0
    for signal, normalized, score in accepted:
        key = (
            normalized,
            signal.platform,
            signal.region,
            signal.language,
            signal.source_name.strip(),
        )
        item = existing.get(key)
        if item is None:
            item = KeywordTrendSignal(
                workspace_id=workspace_id,
                normalized_keyword=normalized,
            )
            db.add(item)
            existing[key] = item
            inserted += 1
        else:
            updated += 1
        item.keyword = signal.keyword.strip()
        item.platform = signal.platform
        item.region = signal.region
        item.language = signal.language
        item.source_name = signal.source_name.strip()
        item.source_type = signal.source_type.strip()
        item.score = score
        item.rank = signal.rank
        item.momentum = signal.momentum
        item.evidence_note = signal.evidence_note
        item.observed_at = signal.observed_at
        item.expires_at = signal.expires_at

    await db.flush()
    succeeded = sum(result.status == "succeeded" for result in results)
    return KeywordSignalRefreshResponse(
        workspace_id=workspace_id,
        platform=platform,
        region=region,
        language=language,
        refreshed_at=refreshed_at,
        providers_attempted=len(results),
        providers_succeeded=succeeded,
        providers_failed=len(results) - succeeded,
        inserted=inserted,
        updated=updated,
        provider_results=results,
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_keyword(value: str) -> str:
    return " ".join(value.casefold().split())


def _collective_momentum(score: float) -> str:
    if score >= 70:
        return "rising"
    if score >= 40:
        return "stable"
    return "falling"


def _quantize_collective_score(score: float) -> float:
    return min(100.0, max(0.0, round(score / 5.0) * 5.0))


def _contributor_cohort(count: int) -> str:
    if count >= 50:
        return "50+"
    if count >= 10:
        return "10-49"
    return "3-9"


async def set_collective_intelligence_preference(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    enabled: bool,
) -> CollectiveIntelligencePreferenceResponse:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise ValueError("workspace does not exist")
    workspace.collective_intelligence_enabled = enabled
    await db.flush()
    return CollectiveIntelligencePreferenceResponse(
        workspace_id=workspace_id,
        enabled=enabled,
    )


async def list_collective_keyword_trends(
    db: AsyncSession,
    workspace_id: UUID,
    parameters: CollectiveKeywordQueryParameters,
    *,
    now: datetime | None = None,
) -> CollectiveKeywordSignalListResponse:
    """Return k-thresholded aggregates without contributor identities."""
    generated_at = now or utcnow()
    preference_result = await db.execute(
        select(Workspace.collective_intelligence_enabled).where(
            Workspace.id == workspace_id
        )
    )
    enabled = preference_result.scalar_one_or_none()
    if enabled is not True:
        return CollectiveKeywordSignalListResponse(
            workspace_id=workspace_id,
            generated_at=generated_at,
            collective_intelligence_enabled=False,
            minimum_contributing_workspaces=3,
            items=[],
        )

    policy = CollectiveIntelligencePolicy(
        window_hours=parameters.window_hours,
    )
    cutoff = generated_at - timedelta(hours=policy.window_hours)
    contribution_rank = func.row_number().over(
        partition_by=(
            KeywordTrendSignal.workspace_id,
            KeywordTrendSignal.normalized_keyword,
            KeywordTrendSignal.platform,
            KeywordTrendSignal.region,
            KeywordTrendSignal.language,
        ),
        order_by=(
            KeywordTrendSignal.score.desc(),
            KeywordTrendSignal.observed_at.desc(),
        ),
    ).label("contribution_rank")
    contributions = select(
        KeywordTrendSignal.workspace_id.label("contributor_id"),
        KeywordTrendSignal.normalized_keyword.label("keyword"),
        KeywordTrendSignal.platform.label("platform"),
        KeywordTrendSignal.region.label("region"),
        KeywordTrendSignal.language.label("language"),
        KeywordTrendSignal.score.label("score"),
        KeywordTrendSignal.source_name.label("source_name"),
        KeywordTrendSignal.observed_at.label("observed_at"),
        KeywordTrendSignal.expires_at.label("expires_at"),
        contribution_rank,
    ).join(
        Workspace,
        Workspace.id == KeywordTrendSignal.workspace_id,
    ).where(
        Workspace.collective_intelligence_enabled.is_(True),
        KeywordTrendSignal.expires_at > generated_at,
        KeywordTrendSignal.observed_at >= cutoff,
    )
    if parameters.platform:
        contributions = contributions.where(
            KeywordTrendSignal.platform == parameters.platform
        )
    if parameters.region:
        contributions = contributions.where(
            KeywordTrendSignal.region == parameters.region
        )
    if parameters.language:
        contributions = contributions.where(
            KeywordTrendSignal.language == parameters.language
        )
    if parameters.query:
        contributions = contributions.where(
            KeywordTrendSignal.normalized_keyword.contains(
                normalize_keyword(parameters.query)
            )
        )
    clipped = contributions.cte("clipped_collective_contributions")
    workspace_count = func.count(
        func.distinct(clipped.c.contributor_id)
    )
    average_score = func.avg(clipped.c.score)
    aggregate = select(
        clipped.c.keyword,
        clipped.c.platform,
        clipped.c.region,
        clipped.c.language,
        average_score.label("aggregate_score"),
        workspace_count.label("workspace_count"),
        func.count(func.distinct(clipped.c.source_name)).label(
            "source_count"
        ),
        func.max(clipped.c.observed_at).label("observed_at"),
        func.min(clipped.c.expires_at).label("expires_at"),
    ).where(
        clipped.c.contribution_rank
        <= policy.maximum_contributions_per_workspace
    ).group_by(
        clipped.c.keyword,
        clipped.c.platform,
        clipped.c.region,
        clipped.c.language,
    ).having(
        workspace_count >= policy.minimum_contributing_workspaces
    ).order_by(
        average_score.desc(),
        func.max(clipped.c.observed_at).desc(),
        clipped.c.keyword,
    ).limit(parameters.limit)
    result = await db.execute(aggregate)
    items = []
    for row in result.all():
        score = _quantize_collective_score(
            float(row.aggregate_score)
        )
        items.append(CollectiveKeywordSignalResponse(
            keyword=row.keyword,
            platform=row.platform,
            region=row.region,
            language=row.language,
            score=score,
            momentum=_collective_momentum(score),
            observed_at=row.observed_at,
            expires_at=row.expires_at,
            contributor_cohort=_contributor_cohort(
                row.workspace_count
            ),
            source_diversity=(
                "multiple"
                if row.source_count > 1
                else "single"
            ),
            aggregation_window_hours=policy.window_hours,
        ))
    return CollectiveKeywordSignalListResponse(
        workspace_id=workspace_id,
        generated_at=generated_at,
        collective_intelligence_enabled=True,
        minimum_contributing_workspaces=(
            policy.minimum_contributing_workspaces
        ),
        items=items,
    )


def serialize_signal(
    signal: KeywordTrendSignal,
    *,
    now: datetime,
) -> KeywordTrendSignalResponse:
    return KeywordTrendSignalResponse(
        id=signal.id,
        keyword=signal.keyword,
        platform=signal.platform,
        region=signal.region,
        language=signal.language,
        source_name=signal.source_name,
        source_type=signal.source_type,
        score=signal.score,
        rank=signal.rank,
        momentum=signal.momentum,
        evidence_note=signal.evidence_note,
        observed_at=signal.observed_at,
        expires_at=signal.expires_at,
        stale=signal.expires_at <= now,
    )


async def list_keyword_trend_signals(
    db: AsyncSession,
    workspace_id: UUID,
    parameters: KeywordTrendQueryParameters,
    *,
    now: datetime | None = None,
) -> KeywordTrendSignalListResponse:
    generated_at = now or utcnow()
    statement = select(KeywordTrendSignal).where(
        KeywordTrendSignal.workspace_id == workspace_id
    )

    if parameters.platform:
        statement = statement.where(
            KeywordTrendSignal.platform == parameters.platform
        )
    if parameters.region:
        statement = statement.where(
            KeywordTrendSignal.region == parameters.region
        )
    if parameters.language:
        statement = statement.where(
            KeywordTrendSignal.language == parameters.language
        )
    if parameters.query:
        statement = statement.where(
            KeywordTrendSignal.normalized_keyword.contains(
                normalize_keyword(parameters.query)
            )
        )
    if not parameters.include_stale:
        statement = statement.where(
            KeywordTrendSignal.expires_at > generated_at
        )

    statement = statement.order_by(
        KeywordTrendSignal.score.desc(),
        KeywordTrendSignal.observed_at.desc(),
    ).limit(parameters.limit)
    result = await db.execute(statement)
    signals = result.scalars().all()

    return KeywordTrendSignalListResponse(
        workspace_id=workspace_id,
        generated_at=generated_at,
        stale_results_included=parameters.include_stale,
        items=[
            serialize_signal(signal, now=generated_at)
            for signal in signals
        ],
    )
