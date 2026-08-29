import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_intelligence import KeywordTrendSignal
from app.schemas.keyword_intelligence import (
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
