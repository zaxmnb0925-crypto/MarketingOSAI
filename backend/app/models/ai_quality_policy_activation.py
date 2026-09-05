import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class AIQualityPolicyActivationMode(str, enum.Enum):
    shadow = "shadow"
    enforced = "enforced"


class AIQualityPolicyActivationStatus(str, enum.Enum):
    active = "active"
    superseded = "superseded"
    rolled_back = "rolled_back"
    expired = "expired"


class AIQualityPolicyActivationAction(str, enum.Enum):
    activated = "activated"
    promoted = "promoted"
    superseded = "superseded"
    rolled_back = "rolled_back"


class AIQualityPolicyActivation(Base):
    __tablename__ = "ai_quality_policy_activations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "brand_id", "version",
            name="uq_ai_quality_activation_scope_version",
        ),
        UniqueConstraint(
            "workspace_id", "brand_id", "idempotency_key",
            name="uq_ai_quality_activation_scope_idempotency",
        ),
        CheckConstraint("version > 0", name="ck_ai_quality_activation_version"),
        CheckConstraint(
            "policy_version > 0", name="ck_ai_quality_activation_policy_version"
        ),
        CheckConstraint(
            "minimum_quality_score >= 0 AND minimum_quality_score <= 100",
            name="ck_ai_quality_activation_minimum_score",
        ),
        CheckConstraint(
            "minimum_cohort_size >= 3 AND minimum_cohort_size <= 1000",
            name="ck_ai_quality_activation_minimum_cohort",
        ),
        CheckConstraint(
            "maximum_workspace_contribution >= 1 "
            "AND maximum_workspace_contribution <= 100",
            name="ck_ai_quality_activation_workspace_clip",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > effective_at",
            name="ck_ai_quality_activation_time_window",
        ),
        Index(
            "uq_ai_quality_activation_one_active_scope",
            "workspace_id", "brand_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_recommendations.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[AIQualityPolicyActivationMode] = mapped_column(
        Enum(AIQualityPolicyActivationMode, name="ai_quality_policy_activation_mode"),
        nullable=False,
    )
    status: Mapped[AIQualityPolicyActivationStatus] = mapped_column(
        Enum(
            AIQualityPolicyActivationStatus,
            name="ai_quality_policy_activation_status",
        ),
        nullable=False,
    )
    minimum_quality_score: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_cohort_size: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_workspace_contribution: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    supersedes_activation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    rolled_back_to_activation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False,
    )


class AIQualityPolicyActivationAudit(Base):
    __tablename__ = "ai_quality_policy_activation_audits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    activation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AIQualityPolicyActivationAction] = mapped_column(
        Enum(AIQualityPolicyActivationAction, name="ai_quality_policy_activation_action"),
        nullable=False,
    )
    previous_activation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_quality_policy_activations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
