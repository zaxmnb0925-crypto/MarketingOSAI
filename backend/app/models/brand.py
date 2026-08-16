import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Brand(Base):
    __tablename__ = "brands"

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

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    industry: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tone: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    target_audience: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    brand_voice: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    value_proposition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    products_services: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    keywords: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    forbidden_words: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    default_cta: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    language: Mapped[str] = mapped_column(
        String(20),
        default="zh-TW",
        nullable=False,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    brand_guidelines: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    workspace = relationship(
        "Workspace",
        back_populates="brands",
    )
