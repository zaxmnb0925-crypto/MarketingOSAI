import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KeywordTrendSignal(Base):
    __tablename__ = "keyword_trend_signals"
    __table_args__ = (
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_keyword_trend_score_range",
        ),
        CheckConstraint(
            "rank IS NULL OR rank > 0",
            name="ck_keyword_trend_rank_positive",
        ),
        CheckConstraint(
            "expires_at > observed_at",
            name="ck_keyword_trend_expiry_after_observation",
        ),
        Index(
            "ix_keyword_trend_workspace_scope",
            "workspace_id",
            "platform",
            "region",
            "language",
            "observed_at",
        ),
        Index(
            "ix_keyword_trend_workspace_expiry",
            "workspace_id",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_keyword: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    region: Mapped[str] = mapped_column(String(16), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    momentum: Mapped[str | None] = mapped_column(String(20), nullable=True)
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
