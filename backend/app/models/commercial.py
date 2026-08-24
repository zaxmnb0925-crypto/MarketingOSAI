import enum
import uuid
from datetime import datetime, timezone

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
from sqlalchemy.dialects.postgresql import (
    JSONB,
    UUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class PlatformAdminRole(str, enum.Enum):
    support = "support"
    billing_admin = "billing_admin"
    subscription_admin = "subscription_admin"
    super_admin = "super_admin"


PLATFORM_ADMIN_ROLES = tuple(
    item.value
    for item in PlatformAdminRole
)


class PlatformAdminMembership(Base):
    __tablename__ = "platform_admin_memberships"

    __table_args__ = (
        CheckConstraint(
            "role IN ("
            "'support', "
            "'billing_admin', "
            "'subscription_admin', "
            "'super_admin'"
            ")",
            name=(
                "ck_platform_admin_memberships_"
                "role"
            ),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    role: Mapped[str] = mapped_column(
        String(32),
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

    revoked_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"
    refunded = "refunded"


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name=(
                "uq_payment_records_"
                "workspace_idempotency"
            ),
        ),
        CheckConstraint(
            "status IN ("
            "'pending', "
            "'confirmed', "
            "'rejected', "
            "'refunded'"
            ")",
            name="ck_payment_records_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    #
    # WorkspaceSubscription is a lifetime Workspace
    # aggregate. Its workspace_id is the relationship
    # identity; there is no subscription-instance id.
    #
    workspace_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspace_subscriptions.workspace_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="manual",
    )

    method: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    amount_minor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentStatus.pending.value,
    )

    received_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    confirmed_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    confirmed_by_admin_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    external_reference: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    customer_note: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    internal_note: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
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


class AdminSubscriptionAudit(Base):
    __tablename__ = "admin_subscription_audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    workspace_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspace_subscriptions.workspace_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    payment_record_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "payment_records.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )

    actor_user_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    actor_admin_role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    support_note: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    before_snapshot_json: Mapped[
        dict
    ] = mapped_column(
        JSONB,
        nullable=False,
    )

    after_snapshot_json: Mapped[
        dict
    ] = mapped_column(
        JSONB,
        nullable=False,
    )

    request_id: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
