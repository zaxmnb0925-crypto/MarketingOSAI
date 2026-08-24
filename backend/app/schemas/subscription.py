from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class PlanResponse(BaseModel):
    code: str
    name: str
    price_twd: int
    monthly_credits: int
    is_active: bool
    is_public: bool
    list_price_minor: int
    promotional_price_minor: int | None
    currency: str

    model_config = ConfigDict(from_attributes=True)


class ChangePlanRequest(BaseModel):
    plan_code: str

    @field_validator("plan_code")
    @classmethod
    def normalize_plan_code(cls, value: str) -> str:
        return value.strip().lower()


class WorkspaceSubscriptionResponse(BaseModel):
    workspace_id: UUID
    plan_code: str
    plan_name: str
    price_twd: int
    monthly_credits: int
    balance: int
    lifetime_used: int
    credits_granted: int
    credits_used: int
    cycle_start: datetime
    cycle_end: datetime
    starts_at: datetime
    expires_at: datetime | None
    renewal_price_minor: int
    billing_currency: str
    status: str
    auto_renew: bool
