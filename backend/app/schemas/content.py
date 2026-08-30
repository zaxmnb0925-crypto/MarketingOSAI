from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_generation import (
    ContentPlatform,
    ContentStatus,
)
from app.models.ai_answer_feedback import AnswerFeedbackReason
from app.models.ai_quality_policy import AIQualityPolicyStatus


class ContentPreviewRequest(BaseModel):
    platform: ContentPlatform

    topic: str = Field(
        min_length=1,
        max_length=500,
    )

    objective: str | None = Field(
        default=None,
        max_length=300,
    )


class ContentGenerationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    platform: ContentPlatform
    topic: str
    objective: str | None
    status: ContentStatus
    prompt: str | None
    generated_content: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    error_message: str | None


class CustomerContentGenerationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    platform: ContentPlatform
    topic: str
    objective: str | None
    status: ContentStatus
    generated_content: str | None
    created_at: datetime
    updated_at: datetime


class PromptPreviewResponse(BaseModel):
    generation: CustomerContentGenerationResponse
    forbidden_word_hits: list[str]


class GenerateContentResponse(BaseModel):
    generation: CustomerContentGenerationResponse
    forbidden_word_hits: list[str]


class AnswerQualitySummary(BaseModel):
    score: int = Field(ge=0, le=100)
    disclosure: str | None = None


class AnswerFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    reason: AnswerFeedbackReason
    comment: str | None = Field(default=None, max_length=500)


class AnswerFeedbackResponse(BaseModel):
    generation_id: UUID
    rating: int
    reason: AnswerFeedbackReason
    comment: str | None
    updated_at: datetime


class AIQualityPolicyDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: AIQualityPolicyStatus
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRecommendationResponse(BaseModel):
    id: UUID
    version: int
    status: AIQualityPolicyStatus
    minimum_quality_score: int = Field(ge=0, le=100)
    minimum_cohort_size: int = Field(ge=3, le=1000)
    maximum_workspace_contribution: int = Field(ge=1, le=100)
    observation_count: int
    distinct_workspace_count: int
    average_quality_score: Decimal
    average_rating: Decimal
    confidence_score: int = Field(ge=0, le=100)
    recommendation_reason: str
    provenance: str
    requires_human_approval: bool = True
    activation_performed: bool = False
    approved_at: datetime | None
    created_at: datetime
