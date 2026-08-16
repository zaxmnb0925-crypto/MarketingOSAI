from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)

    industry: str | None = Field(
        default=None,
        max_length=100,
    )

    website: HttpUrl | None = None
    description: str | None = None

    tone: str | None = Field(
        default=None,
        max_length=100,
    )

    target_audience: str | None = None
    brand_voice: str | None = None
    value_proposition: str | None = None
    products_services: str | None = None
    keywords: str | None = None
    forbidden_words: str | None = None
    default_cta: str | None = None

    language: str = Field(
        default="zh-TW",
        min_length=2,
        max_length=20,
    )

    country: str | None = Field(
        default=None,
        max_length=100,
    )

    brand_guidelines: str | None = None


class BrandUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    industry: str | None = Field(
        default=None,
        max_length=100,
    )

    website: HttpUrl | None = None
    description: str | None = None

    tone: str | None = Field(
        default=None,
        max_length=100,
    )

    target_audience: str | None = None
    brand_voice: str | None = None
    value_proposition: str | None = None
    products_services: str | None = None
    keywords: str | None = None
    forbidden_words: str | None = None
    default_cta: str | None = None

    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=20,
    )

    country: str | None = Field(
        default=None,
        max_length=100,
    )

    brand_guidelines: str | None = None


class BrandResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    industry: str | None
    website: str | None
    description: str | None
    tone: str | None
    target_audience: str | None
    brand_voice: str | None
    value_proposition: str | None
    products_services: str | None
    keywords: str | None
    forbidden_words: str | None
    default_cta: str | None
    language: str
    country: str | None
    brand_guidelines: str | None
