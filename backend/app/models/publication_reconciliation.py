import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class PublicationReconciliationDecision(str, enum.Enum):
    confirmed_published = "confirmed_published"
    confirmed_failed = "confirmed_failed"
    remain_unresolved = "remain_unresolved"


class PublicationReconciliation(Base):
    __tablename__ = "publication_reconciliations"

    __table_args__ = (
        UniqueConstraint(
            "publication_id",
            "idempotency_key",
            name="uq_publication_reconciliations_publication_idempotency",
        ),
        Index(
            "ix_publication_reconciliations_publication_created",
            "publication_id",
            "created_at",
        ),
        Index(
            "ix_publication_reconciliations_workspace_created",
            "workspace_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    operator_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    decision: Mapped[PublicationReconciliationDecision] = mapped_column(
        Enum(
            PublicationReconciliationDecision,
            name="publication_reconciliation_decision",
        ),
        nullable=False,
    )

    publish_attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    provider_post_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_permalink: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    evidence_note: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )
