from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CommercialPriceSelection(str, Enum):
    list = "list"
    promotion = "promotion"


class FreeTransitionReason(str, Enum):
    effective_cancellation = "effective_cancellation"
    expiry = "expiry"


class ManualPaymentCreateRequest(BaseModel):
    method: str = Field(min_length=1, max_length=64)
    amount_minor: int = Field(gt=0)
    currency: str = Field(default="TWD", min_length=3, max_length=3)
    received_at: datetime | None = None
    external_reference: str | None = Field(default=None, max_length=255)
    customer_note: str | None = None
    internal_note: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=128)

    @field_validator("method", "idempotency_key")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("received_at")
    @classmethod
    def normalize_received_at(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        return value.astimezone(timezone.utc)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if value != "TWD":
            raise ValueError("Only TWD is currently supported")
        return value


class PaymentConfirmationRequest(BaseModel):
    target_plan_code: str = Field(min_length=1, max_length=32)
    price_selection: CommercialPriceSelection = CommercialPriceSelection.list
    reason: str = Field(min_length=1)
    request_id: str | None = Field(default=None, max_length=128)

    @field_validator("target_plan_code")
    @classmethod
    def normalize_target_plan_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value.lower()

    @field_validator("reason")
    @classmethod
    def strip_confirmation_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class SubscriptionActionRequest(BaseModel):
    reason: str = Field(min_length=1)
    request_id: str | None = Field(default=None, max_length=128)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be blank")
        return value


class TransitionToFreeRequest(SubscriptionActionRequest):
    transition: FreeTransitionReason


class PaymentRecordResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    source: str
    method: str
    amount_minor: int
    currency: str
    status: str
    received_at: datetime | None
    confirmed_at: datetime | None
    confirmed_by_admin_user_id: UUID | None
    external_reference: str | None
    customer_note: str | None
    internal_note: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformSubscriptionResponse(BaseModel):
    workspace_id: UUID
    plan_code: str
    status: str
    starts_at: datetime
    expires_at: datetime | None
    renewal_price_minor: int
    billing_currency: str
    pricing_source: str | None
    entitlement_version: int
    suspended_at: datetime | None
    cancelled_at: datetime | None
    cancellation_effective_at: datetime | None
    commercial_term_composition_v1: dict[str, Any] | None = None

    model_config = {"from_attributes": True}


class PaymentConfirmationResponse(BaseModel):
    payment: PaymentRecordResponse
    subscription: PlatformSubscriptionResponse
    idempotent_replay: bool = False
