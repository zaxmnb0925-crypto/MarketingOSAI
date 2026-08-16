import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class ContentPlatform(str, enum.Enum):
    facebook = "facebook"
    instagram = "instagram"
    threads = "threads"
    linkedin = "linkedin"
    x = "x"
    google_business = "google_business"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    completed = "completed"
    failed = "failed"


class ContentGeneration(Base):
    __tablename__ = "content_generations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    platform: Mapped[ContentPlatform] = mapped_column(
        Enum(
            ContentPlatform,
            name="content_platform",
        ),
        nullable=False,
    )

    topic: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    objective: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    status: Mapped[ContentStatus] = mapped_column(
        Enum(
            ContentStatus,
            name="content_status",
        ),
        default=ContentStatus.draft,
        nullable=False,
    )

    prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    generated_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
