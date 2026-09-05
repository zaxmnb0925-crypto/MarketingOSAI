"""add AI quality policy effect observation governance

Revision ID: e9a4c3b7d210
Revises: d8f3b2a6c190
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e9a4c3b7d210"
down_revision: Union[str, None] = "d8f3b2a6c190"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    effect_state = postgresql.ENUM("stable", "watch", "degraded", name="ai_quality_policy_effect_state", create_type=False)
    action = postgresql.ENUM("no_change", "investigate", "rollback", name="ai_quality_policy_degradation_action", create_type=False)
    review_status = postgresql.ENUM("pending_review", "accepted", "dismissed", name="ai_quality_policy_degradation_status", create_type=False)
    effect_state.create(op.get_bind(), checkfirst=True)
    action.create(op.get_bind(), checkfirst=True)
    review_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_quality_policy_effect_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("minimum_cohort_size", sa.Integer(), nullable=False),
        sa.Column("maximum_workspace_contribution", sa.Integer(), nullable=False),
        sa.Column("baseline_quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("observed_quality_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("quality_delta", sa.Numeric(6, 2), nullable=False),
        sa.Column("baseline_failure_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("observed_failure_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("consecutive_degraded_windows", sa.Integer(), nullable=False),
        sa.Column("state", effect_state, nullable=False),
        sa.Column("provenance", sa.String(100), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("observation_count >= minimum_cohort_size", name="ck_ai_quality_effect_minimum_cohort"),
        sa.CheckConstraint("minimum_cohort_size >= 3 AND minimum_cohort_size <= 1000", name="ck_ai_quality_effect_cohort_bound"),
        sa.CheckConstraint("maximum_workspace_contribution >= 1 AND maximum_workspace_contribution <= 100", name="ck_ai_quality_effect_workspace_clip"),
        sa.CheckConstraint("baseline_quality_score >= 0 AND baseline_quality_score <= 100", name="ck_ai_quality_effect_baseline_score"),
        sa.CheckConstraint("observed_quality_score >= 0 AND observed_quality_score <= 100", name="ck_ai_quality_effect_observed_score"),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ai_quality_effect_confidence"),
        sa.CheckConstraint("baseline_failure_rate >= 0 AND baseline_failure_rate <= 1", name="ck_ai_quality_effect_baseline_failure_rate"),
        sa.CheckConstraint("observed_failure_rate >= 0 AND observed_failure_rate <= 1", name="ck_ai_quality_effect_observed_failure_rate"),
        sa.CheckConstraint("consecutive_degraded_windows >= 0", name="ck_ai_quality_effect_degraded_windows"),
        sa.CheckConstraint("window_ended_at > window_started_at", name="ck_ai_quality_effect_window"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "brand_id", "activation_id", "window_started_at", name="uq_ai_quality_effect_scope_window"),
    )
    for column in ("workspace_id", "brand_id", "activation_id"):
        op.create_index(f"ix_ai_quality_effect_{column}", "ai_quality_policy_effect_observations", [column])
    op.create_table(
        "ai_quality_policy_degradation_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", action, nullable=False),
        sa.Column("status", review_status, nullable=False),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ai_quality_degradation_confidence"),
        sa.ForeignKeyConstraint(["observation_id"], ["ai_quality_policy_effect_observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("observation_id", name="uq_ai_quality_degradation_observation"),
    )
    for column in ("observation_id", "workspace_id", "brand_id"):
        op.create_index(f"ix_ai_quality_degradation_{column}", "ai_quality_policy_degradation_recommendations", [column])


def downgrade() -> None:
    op.drop_table("ai_quality_policy_degradation_recommendations")
    op.drop_table("ai_quality_policy_effect_observations")
    postgresql.ENUM(name="ai_quality_policy_degradation_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_degradation_action").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_effect_state").drop(op.get_bind(), checkfirst=True)
