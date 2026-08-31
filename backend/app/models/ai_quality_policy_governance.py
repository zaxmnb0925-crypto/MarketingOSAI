import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class AIQualityPolicyGovernanceCaseStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    rejected = "rejected"
    voided = "voided"


class AIQualityPolicyGovernanceCaseAction(str, enum.Enum):
    opened = "opened"
    closed = "closed"
    rejected = "rejected"
    voided = "voided"


class AIQualityPolicyGovernanceEvidenceType(str, enum.Enum):
    remediation = "remediation"
    degradation = "degradation"
    observation = "observation"
    activation = "activation"


class AIQualityPolicyGovernanceCase(Base):
    __tablename__ = "ai_quality_policy_governance_cases"
    __table_args__ = (
        UniqueConstraint("remediation_id", name="uq_ai_quality_governance_case_remediation"),
        UniqueConstraint("workspace_id", "brand_id", "idempotency_key", name="uq_ai_quality_governance_case_scope_idempotency"),
        CheckConstraint("policy_version > 0", name="ck_ai_quality_governance_case_policy_version"),
        CheckConstraint("evidence_item_count >= 1 AND evidence_item_count <= 100", name="ck_ai_quality_governance_case_evidence_count"),
        CheckConstraint("length(evidence_manifest_sha256) = 64", name="ck_ai_quality_governance_case_manifest_sha"),
        CheckConstraint("closed_at IS NULL OR closed_by_user_id IS NOT NULL", name="ck_ai_quality_governance_case_human_closure"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    remediation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_remediations.id", ondelete="RESTRICT"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True)
    activation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    remediation_status_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[AIQualityPolicyGovernanceCaseStatus] = mapped_column(Enum(AIQualityPolicyGovernanceCaseStatus, name="ai_quality_policy_governance_case_status"), nullable=False, default=AIQualityPolicyGovernanceCaseStatus.open)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    governance_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    closure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AIQualityPolicyGovernanceEvidenceItem(Base):
    __tablename__ = "ai_quality_policy_governance_evidence_items"
    __table_args__ = (
        UniqueConstraint("case_id", "sequence", name="uq_ai_quality_governance_evidence_sequence"),
        UniqueConstraint("case_id", "source_table", "source_record_id", name="uq_ai_quality_governance_evidence_source"),
        CheckConstraint("sequence >= 1 AND sequence <= 100", name="ck_ai_quality_governance_evidence_sequence"),
        CheckConstraint("length(payload_sha256) = 64", name="ck_ai_quality_governance_evidence_sha"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_governance_cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_type: Mapped[AIQualityPolicyGovernanceEvidenceType] = mapped_column(Enum(AIQualityPolicyGovernanceEvidenceType, name="ai_quality_policy_governance_evidence_type"), nullable=False)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    source_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_state: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AIQualityPolicyGovernanceCaseAudit(Base):
    __tablename__ = "ai_quality_policy_governance_case_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_quality_policy_governance_cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[AIQualityPolicyGovernanceCaseAction] = mapped_column(Enum(AIQualityPolicyGovernanceCaseAction, name="ai_quality_policy_governance_case_action"), nullable=False)
    previous_status: Mapped[AIQualityPolicyGovernanceCaseStatus | None] = mapped_column(Enum(AIQualityPolicyGovernanceCaseStatus, name="ai_quality_policy_governance_case_status", create_type=False), nullable=True)
    new_status: Mapped[AIQualityPolicyGovernanceCaseStatus] = mapped_column(Enum(AIQualityPolicyGovernanceCaseStatus, name="ai_quality_policy_governance_case_status", create_type=False), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
