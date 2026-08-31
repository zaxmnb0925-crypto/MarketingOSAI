"""add AI quality policy human remediation governance

Revision ID: f0b5d4c8e320
Revises: e9a4c3b7d210
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f0b5d4c8e320"
down_revision: Union[str, None] = "e9a4c3b7d210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status = postgresql.ENUM("proposed", "approved", "rejected", "executing", "observation", "recovered", "failed", name="ai_quality_policy_remediation_status", create_type=False)
    action = postgresql.ENUM("proposed", "approved", "rejected", "execution_started", "observation_started", "recovered", "failed", name="ai_quality_policy_remediation_action", create_type=False)
    status.create(op.get_bind(), checkfirst=True)
    action.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_quality_policy_remediations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("degradation_recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_activation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_activation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_policy_version", sa.Integer(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("proposal_reason", sa.String(200), nullable=False),
        sa.Column("decision_reason", sa.String(200), nullable=True),
        sa.Column("execution_reason", sa.String(200), nullable=True),
        sa.Column("closure_reason", sa.String(200), nullable=True),
        sa.Column("observation_window_count", sa.Integer(), nullable=False),
        sa.Column("recovery_threshold", sa.Integer(), nullable=False),
        sa.Column("proposed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("executed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observation_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expected_policy_version > 0", name="ck_ai_quality_remediation_policy_version"),
        sa.CheckConstraint("observation_window_count >= 1 AND observation_window_count <= 100", name="ck_ai_quality_remediation_observation_windows"),
        sa.CheckConstraint("recovery_threshold >= 0 AND recovery_threshold <= 100", name="ck_ai_quality_remediation_recovery_threshold"),
        sa.CheckConstraint("observation_ended_at IS NULL OR observation_started_at IS NOT NULL", name="ck_ai_quality_remediation_observation_start"),
        sa.CheckConstraint("observation_ended_at IS NULL OR observation_ended_at > observation_started_at", name="ck_ai_quality_remediation_observation_window"),
        sa.ForeignKeyConstraint(["degradation_recommendation_id"], ["ai_quality_policy_degradation_recommendations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["proposed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["executed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("degradation_recommendation_id", name="uq_ai_quality_remediation_degradation"),
        sa.UniqueConstraint("workspace_id", "brand_id", "idempotency_key", name="uq_ai_quality_remediation_scope_idempotency"),
    )
    for column in ("degradation_recommendation_id", "workspace_id", "brand_id"):
        op.create_index(f"ix_ai_quality_remediation_{column}", "ai_quality_policy_remediations", [column])
    op.create_table(
        "ai_quality_policy_remediation_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", action, nullable=False),
        sa.Column("previous_status", status, nullable=True),
        sa.Column("new_status", status, nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["remediation_id"], ["ai_quality_policy_remediations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quality_remediation_audit_remediation_id", "ai_quality_policy_remediation_audits", ["remediation_id"])
    op.create_index("ix_ai_quality_remediation_audit_workspace_id", "ai_quality_policy_remediation_audits", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ai_quality_policy_remediation_audits")
    op.drop_table("ai_quality_policy_remediations")
    postgresql.ENUM(name="ai_quality_policy_remediation_action").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_remediation_status").drop(op.get_bind(), checkfirst=True)
