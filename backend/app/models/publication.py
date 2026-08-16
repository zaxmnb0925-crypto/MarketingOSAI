import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublicationStatus(
    str,
    enum.Enum,
):
    draft = "draft"
    approved = "approved"
    publishing = "publishing"
    published = "published"
    failed = "failed"
    cancelled = "cancelled"


class Publication(Base):
    __tablename__ = "publications"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name=(
                "uq_publications_"
                "workspace_idempotency"
            ),
        ),
        Index(
            "ix_publications_workspace_status",
            "workspace_id",
            "status",
        ),
        Index(
            "ix_publications_social_status",
            "social_account_id",
            "status",
        ),
    )

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

    brand_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "brands.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    content_generation_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "content_generations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    social_account_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "social_accounts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    status: Mapped[
        PublicationStatus
    ] = mapped_column(
        Enum(
            PublicationStatus,
            name="publication_status",
        ),
        nullable=False,
        default=PublicationStatus.draft,
    )

    # Snapshot of the exact destination at draft
    # creation time. This keeps the audit trail
    # meaningful even if the SocialAccount is later
    # disconnected or deleted.
    platform: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    target_account_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    target_account_name: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    # Exact content intended for publishing.
    # Publishing must never read live AI output after
    # approval; it publishes this immutable snapshot.
    content_snapshot: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # SHA-256 hex digest of content_snapshot.
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # Protects against duplicate requests/retries.
    # It is unique inside each Workspace, not globally.
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    approved_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    approved_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    #
    # Durable audit of the operator who actually initiated
    # the provider-side publishing attempt.
    #
    publish_triggered_by_user_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    publish_triggered_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    publish_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    provider_post_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    provider_permalink: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    #
    # Durable state-machine marker for an ambiguous provider
    # outcome requiring explicit operator reconciliation.
    #
    reconciliation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Must contain sanitized operational information
    # only. Provider response bodies/tokens must never
    # be stored here.
    last_error: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    published_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
