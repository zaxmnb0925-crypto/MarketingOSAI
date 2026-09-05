import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class SubscriptionStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    active = "active"
    suspended = "suspended"
    cancelled = "cancelled"
    expired = "expired"


CANONICAL_SUBSCRIPTION_STATUSES = tuple(
    item.value
    for item in SubscriptionStatus
)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    billing_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="TWD",
    )

    list_price_minor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    promotional_price_minor: Mapped[
        int | None
    ] = mapped_column(
        Integer,
        nullable=True,
    )

    price_display_note: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    manual_quote_required: Mapped[
        bool
    ] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    #
    # Legacy internal accounting fields remain intact.
    # Neither price_twd nor monthly_credits is an
    # authorization input for EntitlementService.
    #
    price_twd: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    monthly_credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class WorkspaceSubscription(Base):
    __tablename__ = "workspace_subscriptions"

    __table_args__ = (
        CheckConstraint(
            "status IN ("
            "'pending_payment', "
            "'active', "
            "'suspended', "
            "'cancelled', "
            "'expired'"
            ")",
            name=(
                "ck_workspace_subscriptions_"
                "canonical_status"
            ),
        ),
        CheckConstraint(
            "((plan_code = 'free' AND expires_at IS NULL) OR "
            "(plan_code <> 'free' AND expires_at IS NOT NULL))",
            name="ck_workspace_subscriptions_commercial_expiry",
        ),
    )

    workspace_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    plan_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey(
            "subscription_plans.code",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    expires_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    activated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    activated_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    suspended_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancellation_effective_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="system",
    )

    entitlement_version: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    renewal_price_minor: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    billing_currency: Mapped[
        str
    ] = mapped_column(
        String(3),
        nullable=False,
        default="TWD",
    )

    pricing_source: Mapped[
        str | None
    ] = mapped_column(
        String(64),
        nullable=True,
    )

    #
    # Legacy cycle/accounting columns remain available
    # until their later, separately reviewed migration.
    #
    cycle_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    cycle_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    credits_granted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    credits_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    auto_renew: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"

    __table_args__ = (
        UniqueConstraint(
            "plan_code",
            "key",
            name=(
                "uq_plan_entitlements_"
                "plan_key"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    plan_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey(
            "subscription_plans.code",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    value_json: Mapped[Any] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
