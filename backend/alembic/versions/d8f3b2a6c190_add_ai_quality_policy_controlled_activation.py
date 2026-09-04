"""add AI quality policy controlled activation

Revision ID: d8f3b2a6c190
Revises: c7e4a1b9d260
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d8f3b2a6c190"
down_revision: Union[str, None] = "c7e4a1b9d260"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    mode = postgresql.ENUM(
        "shadow", "enforced", name="ai_quality_policy_activation_mode",
        create_type=False,
    )
    status = postgresql.ENUM(
        "active", "superseded", "rolled_back", "expired",
        name="ai_quality_policy_activation_status",
        create_type=False,
    )
    action = postgresql.ENUM(
        "activated", "promoted", "superseded", "rolled_back",
        name="ai_quality_policy_activation_action",
        create_type=False,
    )
    mode.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)
    action.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_quality_policy_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("mode", mode, nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("minimum_quality_score", sa.Integer(), nullable=False),
        sa.Column("minimum_cohort_size", sa.Integer(), nullable=False),
        sa.Column("maximum_workspace_contribution", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("supersedes_activation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rolled_back_to_activation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_ai_quality_activation_version"),
        sa.CheckConstraint("policy_version > 0", name="ck_ai_quality_activation_policy_version"),
        sa.CheckConstraint("minimum_quality_score >= 0 AND minimum_quality_score <= 100", name="ck_ai_quality_activation_minimum_score"),
        sa.CheckConstraint("minimum_cohort_size >= 3 AND minimum_cohort_size <= 1000", name="ck_ai_quality_activation_minimum_cohort"),
        sa.CheckConstraint("maximum_workspace_contribution >= 1 AND maximum_workspace_contribution <= 100", name="ck_ai_quality_activation_workspace_clip"),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > effective_at", name="ck_ai_quality_activation_time_window"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["ai_quality_policy_recommendations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["activated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rolled_back_to_activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "brand_id", "version", name="uq_ai_quality_activation_scope_version"),
        sa.UniqueConstraint("workspace_id", "brand_id", "idempotency_key", name="uq_ai_quality_activation_scope_idempotency"),
    )
    op.create_index("ix_ai_quality_activation_workspace_id", "ai_quality_policy_activations", ["workspace_id"])
    op.create_index("ix_ai_quality_activation_brand_id", "ai_quality_policy_activations", ["brand_id"])
    op.create_index("ix_ai_quality_activation_recommendation_id", "ai_quality_policy_activations", ["recommendation_id"])
    op.create_index(
        "uq_ai_quality_activation_one_active_scope",
        "ai_quality_policy_activations",
        ["workspace_id", "brand_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "ai_quality_policy_activation_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", action, nullable=False),
        sa.Column("previous_activation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["previous_activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quality_activation_audit_activation_id", "ai_quality_policy_activation_audits", ["activation_id"])
    op.create_index("ix_ai_quality_activation_audit_workspace_id", "ai_quality_policy_activation_audits", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ai_quality_policy_activation_audits")
    op.drop_index("uq_ai_quality_activation_one_active_scope", table_name="ai_quality_policy_activations")
    op.drop_table("ai_quality_policy_activations")
    postgresql.ENUM(name="ai_quality_policy_activation_action").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_activation_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_activation_mode").drop(op.get_bind(), checkfirst=True)
