import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class PaymentRequestStatus(str, enum.Enum):
    requested = "requested"
    contacted = "contacted"
    payment_pending = "payment_pending"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_plan_code: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PaymentRequestStatus.requested.value,
    )
    customer_note: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    admin_note: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    payment_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
