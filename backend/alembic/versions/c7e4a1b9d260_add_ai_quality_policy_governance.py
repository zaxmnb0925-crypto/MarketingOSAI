"""add AI quality policy governance

Revision ID: c7e4a1b9d260
Revises: 8b2c6d4e1f30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c7e4a1b9d260"
down_revision: Union[str, None] = "8b2c6d4e1f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status = postgresql.ENUM(
        "candidate",
        "approved",
        "rejected",
        "rolled_back",
        name="ai_quality_policy_status",
        create_type=False,
    )
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_quality_policy_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("minimum_quality_score", sa.Integer(), nullable=False),
        sa.Column("minimum_cohort_size", sa.Integer(), nullable=False),
        sa.Column("maximum_workspace_contribution", sa.Integer(), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("distinct_workspace_count", sa.Integer(), nullable=False),
        sa.Column("average_quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("average_rating", sa.Numeric(3, 2), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("recommendation_reason", sa.String(100), nullable=False),
        sa.Column("provenance", sa.String(100), nullable=False),
        sa.Column("baseline_policy_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("minimum_quality_score >= 0 AND minimum_quality_score <= 100", name="ck_ai_quality_policy_minimum_score"),
        sa.CheckConstraint("minimum_cohort_size >= 3 AND minimum_cohort_size <= 1000", name="ck_ai_quality_policy_minimum_cohort"),
        sa.CheckConstraint("maximum_workspace_contribution >= 1 AND maximum_workspace_contribution <= 100", name="ck_ai_quality_policy_workspace_clip"),
        sa.CheckConstraint("observation_count >= minimum_cohort_size", name="ck_ai_quality_policy_observation_cohort"),
        sa.CheckConstraint("distinct_workspace_count >= 3", name="ck_ai_quality_policy_distinct_workspaces"),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ai_quality_policy_confidence"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["baseline_policy_id"], ["ai_quality_policy_recommendations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "brand_id", "version", name="uq_ai_quality_policy_workspace_brand_version"),
    )
    op.create_index("ix_ai_quality_policy_workspace_id", "ai_quality_policy_recommendations", ["workspace_id"])
    op.create_index("ix_ai_quality_policy_brand_id", "ai_quality_policy_recommendations", ["brand_id"])
    op.create_table(
        "ai_quality_policy_decision_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_status", status, nullable=False),
        sa.Column("new_status", status, nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recommendation_id"], ["ai_quality_policy_recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quality_policy_audit_recommendation_id", "ai_quality_policy_decision_audits", ["recommendation_id"])
    op.create_index("ix_ai_quality_policy_audit_workspace_id", "ai_quality_policy_decision_audits", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ai_quality_policy_decision_audits")
    op.drop_table("ai_quality_policy_recommendations")
    postgresql.ENUM(name="ai_quality_policy_status").drop(
        op.get_bind(), checkfirst=True
    )
