from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KeywordTrendSignalResponse(BaseModel):
    id: UUID
    keyword: str
    platform: str
    region: str
    language: str
    source_name: str
    source_type: str
    score: float = Field(ge=0, le=100)
    rank: int | None = Field(default=None, ge=1)
    momentum: str | None
    evidence_note: str | None
    observed_at: datetime
    expires_at: datetime
    stale: bool
    signal_scope: Literal["workspace"] = "workspace"

    model_config = ConfigDict(from_attributes=True)


class KeywordTrendSignalListResponse(BaseModel):
    workspace_id: UUID
    generated_at: datetime
    stale_results_included: bool
    items: list[KeywordTrendSignalResponse]


class KeywordTrendQueryParameters(BaseModel):
    platform: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=16)
    language: str | None = Field(default=None, max_length=20)
    query: str | None = Field(default=None, max_length=100)
    include_stale: bool = False
    limit: int = Field(default=25, ge=1, le=100)


class KeywordSignalRefreshRequest(BaseModel):
    platform: str = Field(min_length=1, max_length=40)
    region: str = Field(min_length=1, max_length=16)
    language: str = Field(min_length=1, max_length=20)


class KeywordProviderRefreshResult(BaseModel):
    provider: str
    status: str
    attempts: int = Field(ge=1, le=3)
    accepted_signals: int = Field(ge=0)
    failure_class: str | None = None


class KeywordSignalRefreshResponse(BaseModel):
    workspace_id: UUID
    platform: str
    region: str
    language: str
    refreshed_at: datetime
    providers_attempted: int = Field(ge=1)
    providers_succeeded: int = Field(ge=0)
    providers_failed: int = Field(ge=0)
    inserted: int = Field(ge=0)
    updated: int = Field(ge=0)
    provider_results: list[KeywordProviderRefreshResult]


class CollectiveKeywordQueryParameters(BaseModel):
    platform: str | None = Field(default=None, max_length=40)
    region: str | None = Field(default=None, max_length=16)
    language: str | None = Field(default=None, max_length=20)
    query: str | None = Field(default=None, max_length=100)
    window_hours: int = Field(default=24, ge=1, le=168)
    limit: int = Field(default=25, ge=1, le=100)

    model_config = ConfigDict(extra="forbid")


class CollectiveKeywordSignalResponse(BaseModel):
    keyword: str
    platform: str
    region: str
    language: str
    score: float = Field(ge=0, le=100)
    momentum: Literal["rising", "stable", "falling"]
    observed_at: datetime
    expires_at: datetime
    contributor_cohort: Literal["3-9", "10-49", "50+"]
    source_diversity: Literal["single", "multiple"]
    aggregation_window_hours: int = Field(ge=1, le=168)
    signal_scope: Literal["collective"] = "collective"
    provenance: Literal[
        "privacy_preserving_aggregate"
    ] = "privacy_preserving_aggregate"


class CollectiveKeywordSignalListResponse(BaseModel):
    workspace_id: UUID
    generated_at: datetime
    collective_intelligence_enabled: bool
    minimum_contributing_workspaces: int = Field(ge=3)
    items: list[CollectiveKeywordSignalResponse]


class CollectiveIntelligencePreferenceRequest(BaseModel):
    enabled: bool


class CollectiveIntelligencePreferenceResponse(BaseModel):
    workspace_id: UUID
    enabled: bool
