import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class AIQualityPolicyStatus(str, enum.Enum):
    candidate = "candidate"
    approved = "approved"
    rejected = "rejected"
    rolled_back = "rolled_back"


class AIQualityPolicyRecommendation(Base):
    """Human-governed policy candidate derived from aggregate metrics only."""

    __tablename__ = "ai_quality_policy_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "brand_id",
            "version",
            name="uq_ai_quality_policy_workspace_brand_version",
        ),
        CheckConstraint(
            "minimum_quality_score >= 0 AND minimum_quality_score <= 100",
            name="ck_ai_quality_policy_minimum_score",
        ),
        CheckConstraint(
            "minimum_cohort_size >= 3 AND minimum_cohort_size <= 1000",
            name="ck_ai_quality_policy_minimum_cohort",
        ),
        CheckConstraint(
            "maximum_workspace_contribution >= 1 "
            "AND maximum_workspace_contribution <= 100",
            name="ck_ai_quality_policy_workspace_clip",
        ),
        CheckConstraint(
            "observation_count >= minimum_cohort_size",
            name="ck_ai_quality_policy_observation_cohort",
        ),
        CheckConstraint(
            "distinct_workspace_count >= 3",
            name="ck_ai_quality_policy_distinct_workspaces",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="ck_ai_quality_policy_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
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
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AIQualityPolicyStatus] = mapped_column(
        Enum(AIQualityPolicyStatus, name="ai_quality_policy_status"),
        default=AIQualityPolicyStatus.candidate,
        nullable=False,
    )
    minimum_quality_score: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_cohort_size: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_workspace_contribution: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_workspace_count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_quality_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    average_rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    provenance: Mapped[str] = mapped_column(
        String(100),
        default="clipped_aggregate_quality_feedback",
        nullable=False,
    )
    baseline_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AIQualityPolicyDecisionAudit(Base):
    __tablename__ = "ai_quality_policy_decision_audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_status: Mapped[AIQualityPolicyStatus] = mapped_column(
        Enum(
            AIQualityPolicyStatus,
            name="ai_quality_policy_status",
        ),
        nullable=False,
    )
    new_status: Mapped[AIQualityPolicyStatus] = mapped_column(
        Enum(
            AIQualityPolicyStatus,
            name="ai_quality_policy_status",
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
