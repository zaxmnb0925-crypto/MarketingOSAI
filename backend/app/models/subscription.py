from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


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


class WorkspaceSubscription(Base):
    __tablename__ = "workspace_subscriptions"

    workspace_id = mapped_column(
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
