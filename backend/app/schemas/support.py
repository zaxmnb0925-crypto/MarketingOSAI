from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SupportConversationCreate(BaseModel):
    category: str = Field(default="general", min_length=1, max_length=64)
    subject: str | None = Field(default=None, max_length=255)
    message: str = Field(min_length=1, max_length=4000)
    payment_request_id: UUID | None = None


class SupportMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class SupportMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_user_id: UUID
    sender_role: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SupportConversationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    payment_request_id: UUID | None
    kind: str
    category: str
    subject: str | None
    status: str
    channel: str
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminSupportConversationResponse(SupportConversationResponse):
    workspace_name: str
    owner_email: str
    owner_full_name: str | None
