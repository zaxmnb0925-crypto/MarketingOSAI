"""add AI quality policy governance evidence and case closure

Revision ID: a1c6e5d9f430
Revises: f0b5d4c8e320
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1c6e5d9f430"
down_revision: Union[str, None] = "f0b5d4c8e320"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    case_status = postgresql.ENUM("open", "closed", "rejected", "voided", name="ai_quality_policy_governance_case_status", create_type=False)
    case_action = postgresql.ENUM("opened", "closed", "rejected", "voided", name="ai_quality_policy_governance_case_action", create_type=False)
    evidence_type = postgresql.ENUM("remediation", "degradation", "observation", "activation", name="ai_quality_policy_governance_evidence_type", create_type=False)
    case_status.create(op.get_bind(), checkfirst=True)
    case_action.create(op.get_bind(), checkfirst=True)
    evidence_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_quality_policy_governance_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("remediation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("remediation_status_snapshot", sa.String(30), nullable=False), sa.Column("status", case_status, nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False), sa.Column("evidence_manifest_sha256", sa.String(64), nullable=False),
        sa.Column("evidence_item_count", sa.Integer(), nullable=False), sa.Column("governance_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("closure_reason", sa.String(300), nullable=True), sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True), sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("policy_version > 0", name="ck_ai_quality_governance_case_policy_version"),
        sa.CheckConstraint("evidence_item_count >= 1 AND evidence_item_count <= 100", name="ck_ai_quality_governance_case_evidence_count"),
        sa.CheckConstraint("length(evidence_manifest_sha256) = 64", name="ck_ai_quality_governance_case_manifest_sha"),
        sa.CheckConstraint("closed_at IS NULL OR closed_by_user_id IS NOT NULL", name="ck_ai_quality_governance_case_human_closure"),
        sa.ForeignKeyConstraint(["remediation_id"], ["ai_quality_policy_remediations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activation_id"], ["ai_quality_policy_activations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("remediation_id", name="uq_ai_quality_governance_case_remediation"),
        sa.UniqueConstraint("workspace_id", "brand_id", "idempotency_key", name="uq_ai_quality_governance_case_scope_idempotency"),
    )
    for column in ("remediation_id", "workspace_id", "brand_id"):
        op.create_index(f"ix_ai_quality_governance_case_{column}", "ai_quality_policy_governance_cases", [column])
    op.create_table(
        "ai_quality_policy_governance_evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("evidence_type", evidence_type, nullable=False), sa.Column("source_table", sa.String(100), nullable=False),
        sa.Column("source_record_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("source_state", sa.String(50), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False), sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1 AND sequence <= 100", name="ck_ai_quality_governance_evidence_sequence"),
        sa.CheckConstraint("length(payload_sha256) = 64", name="ck_ai_quality_governance_evidence_sha"),
        sa.ForeignKeyConstraint(["case_id"], ["ai_quality_policy_governance_cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "sequence", name="uq_ai_quality_governance_evidence_sequence"),
        sa.UniqueConstraint("case_id", "source_table", "source_record_id", name="uq_ai_quality_governance_evidence_source"),
    )
    op.create_index("ix_ai_quality_governance_evidence_case_id", "ai_quality_policy_governance_evidence_items", ["case_id"])
    op.create_index("ix_ai_quality_governance_evidence_workspace_id", "ai_quality_policy_governance_evidence_items", ["workspace_id"])
    op.create_table(
        "ai_quality_policy_governance_case_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", case_action, nullable=False), sa.Column("previous_status", case_status, nullable=True),
        sa.Column("new_status", case_status, nullable=False), sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["ai_quality_policy_governance_cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quality_governance_case_audit_case_id", "ai_quality_policy_governance_case_audits", ["case_id"])
    op.create_index("ix_ai_quality_governance_case_audit_workspace_id", "ai_quality_policy_governance_case_audits", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("ai_quality_policy_governance_case_audits")
    op.drop_table("ai_quality_policy_governance_evidence_items")
    op.drop_table("ai_quality_policy_governance_cases")
    postgresql.ENUM(name="ai_quality_policy_governance_evidence_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_governance_case_action").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="ai_quality_policy_governance_case_status").drop(op.get_bind(), checkfirst=True)
