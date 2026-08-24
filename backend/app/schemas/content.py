from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.content_generation import (
    ContentPlatform,
    ContentStatus,
)


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
