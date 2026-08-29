from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.keyword_intelligence import KeywordTrendSignal
from app.schemas.keyword_intelligence import (
    KeywordTrendQueryParameters,
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
    """Provider contract only; P5-C1 ships no network implementation."""

    async def fetch_signals(
        self,
        *,
        workspace_id: UUID,
        platform: str,
        region: str,
        language: str,
    ) -> list[ProviderKeywordSignal]: ...


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
