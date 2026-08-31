import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class AIQualityPolicyRemediationStatus(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    executing = "executing"
    observation = "observation"
    recovered = "recovered"
    failed = "failed"


class AIQualityPolicyRemediationAction(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"
    execution_started = "execution_started"
    observation_started = "observation_started"
    recovered = "recovered"
    failed = "failed"


class AIQualityPolicyRemediation(Base):
    __tablename__ = "ai_quality_policy_remediations"
    __table_args__ = (
        UniqueConstraint("degradation_recommendation_id", name="uq_ai_quality_remediation_degradation"),
        UniqueConstraint("workspace_id", "brand_id", "idempotency_key", name="uq_ai_quality_remediation_scope_idempotency"),
        CheckConstraint("expected_policy_version > 0", name="ck_ai_quality_remediation_policy_version"),
        CheckConstraint("observation_window_count >= 1 AND observation_window_count <= 100", name="ck_ai_quality_remediation_observation_windows"),
        CheckConstraint("recovery_threshold >= 0 AND recovery_threshold <= 100", name="ck_ai_quality_remediation_recovery_threshold"),
        CheckConstraint("observation_ended_at IS NULL OR observation_started_at IS NOT NULL", name="ck_ai_quality_remediation_observation_start"),
        CheckConstraint("observation_ended_at IS NULL OR observation_ended_at > observation_started_at", name="ck_ai_quality_remediation_observation_window"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    degradation_recommendation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_degradation_recommendations.id", ondelete="RESTRICT"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    source_activation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"), nullable=False)
    target_activation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"), nullable=False)
    expected_policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AIQualityPolicyRemediationStatus] = mapped_column(Enum(AIQualityPolicyRemediationStatus, name="ai_quality_policy_remediation_status"), nullable=False, default=AIQualityPolicyRemediationStatus.proposed)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    proposal_reason: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    execution_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    closure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    observation_window_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recovery_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    executed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observation_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AIQualityPolicyRemediationAudit(Base):
    __tablename__ = "ai_quality_policy_remediation_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    remediation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_remediations.id", ondelete="RESTRICT"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[AIQualityPolicyRemediationAction] = mapped_column(Enum(AIQualityPolicyRemediationAction, name="ai_quality_policy_remediation_action"), nullable=False)
    previous_status: Mapped[AIQualityPolicyRemediationStatus | None] = mapped_column(Enum(AIQualityPolicyRemediationStatus, name="ai_quality_policy_remediation_status", create_type=False), nullable=True)
    new_status: Mapped[AIQualityPolicyRemediationStatus] = mapped_column(Enum(AIQualityPolicyRemediationStatus, name="ai_quality_policy_remediation_status", create_type=False), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
