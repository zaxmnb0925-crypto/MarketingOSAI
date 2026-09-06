from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


_ALLOWED_CATEGORIES = {
    "general",
    "system",
    "login",
    "ai",
    "payment",
    "other",
}


class PublicSupportInquiryCreate(BaseModel):
    email: EmailStr
    category: str = Field(default="general", min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=255)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in _ALLOWED_CATEGORIES:
            raise ValueError("Unsupported support category")
        return normalized

    @field_validator("subject", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("This field cannot be blank")
        return normalized


class PublicSupportInquiryResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminSupportInquiryResponse(BaseModel):
    id: UUID
    email: EmailStr
    category: str
    subject: str
    message: str
    status: str
    channel: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
