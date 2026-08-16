from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PlanResponse(BaseModel):
    code: str
    name: str
    price_twd: int
    monthly_credits: int
    is_active: bool


class ChangePlanRequest(BaseModel):
    plan_code: str


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
    status: str
    auto_renew: bool
