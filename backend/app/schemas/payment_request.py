from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentRequestCreate(BaseModel):
    requested_plan_code: str = Field(min_length=1, max_length=32)
    customer_note: str | None = None


class PaymentRequestResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    requested_plan_code: str
    status: str
    customer_note: str | None
    admin_note: str | None
    payment_record_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
