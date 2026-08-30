import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class AIQualityPolicyEffectState(str, enum.Enum):
    stable = "stable"
    watch = "watch"
    degraded = "degraded"


class AIQualityPolicyDegradationAction(str, enum.Enum):
    no_change = "no_change"
    investigate = "investigate"
    rollback = "rollback"


class AIQualityPolicyDegradationStatus(str, enum.Enum):
    pending_review = "pending_review"
    accepted = "accepted"
    dismissed = "dismissed"


class AIQualityPolicyEffectObservation(Base):
    __tablename__ = "ai_quality_policy_effect_observations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "brand_id", "activation_id", "window_started_at", name="uq_ai_quality_effect_scope_window"),
        CheckConstraint("observation_count >= minimum_cohort_size", name="ck_ai_quality_effect_minimum_cohort"),
        CheckConstraint("minimum_cohort_size >= 3 AND minimum_cohort_size <= 1000", name="ck_ai_quality_effect_cohort_bound"),
        CheckConstraint("maximum_workspace_contribution >= 1 AND maximum_workspace_contribution <= 100", name="ck_ai_quality_effect_workspace_clip"),
        CheckConstraint("baseline_quality_score >= 0 AND baseline_quality_score <= 100", name="ck_ai_quality_effect_baseline_score"),
        CheckConstraint("observed_quality_score >= 0 AND observed_quality_score <= 100", name="ck_ai_quality_effect_observed_score"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ai_quality_effect_confidence"),
        CheckConstraint("baseline_failure_rate >= 0 AND baseline_failure_rate <= 1", name="ck_ai_quality_effect_baseline_failure_rate"),
        CheckConstraint("observed_failure_rate >= 0 AND observed_failure_rate <= 1", name="ck_ai_quality_effect_observed_failure_rate"),
        CheckConstraint("consecutive_degraded_windows >= 0", name="ck_ai_quality_effect_degraded_windows"),
        CheckConstraint("window_ended_at > window_started_at", name="ck_ai_quality_effect_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    activation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"), nullable=False, index=True)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_cohort_size: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_workspace_contribution: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    observed_quality_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    quality_delta: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    baseline_failure_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    observed_failure_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    consecutive_degraded_windows: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[AIQualityPolicyEffectState] = mapped_column(Enum(AIQualityPolicyEffectState, name="ai_quality_policy_effect_state"), nullable=False)
    provenance: Mapped[str] = mapped_column(String(100), nullable=False, default="clipped_aggregate_policy_effects")
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AIQualityPolicyDegradationRecommendation(Base):
    __tablename__ = "ai_quality_policy_degradation_recommendations"
    __table_args__ = (
        UniqueConstraint("observation_id", name="uq_ai_quality_degradation_observation"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ai_quality_degradation_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_effect_observations.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    activation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[AIQualityPolicyDegradationAction] = mapped_column(Enum(AIQualityPolicyDegradationAction, name="ai_quality_policy_degradation_action"), nullable=False)
    status: Mapped[AIQualityPolicyDegradationStatus] = mapped_column(Enum(AIQualityPolicyDegradationStatus, name="ai_quality_policy_degradation_status"), nullable=False, default=AIQualityPolicyDegradationStatus.pending_review)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
