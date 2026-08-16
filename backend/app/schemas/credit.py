from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class CreditAccountResponse(BaseModel):
    workspace_id: UUID
    balance: int
    lifetime_used: int


class CreditLedgerResponse(BaseModel):
    id: UUID
    generation_id: UUID | None
    operation: str
    credits: int
    actual_cost_usd: Decimal | None
    note: str | None
    created_at: datetime
