import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class WorkspaceCreditAccount(Base):
    __tablename__ = "workspace_credit_accounts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    balance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
    )

    lifetime_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
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


class AICreditLedger(Base):
    __tablename__ = "ai_credit_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "content_generations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    operation: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    credits: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    actual_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
