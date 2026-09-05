"""add AI answer quality and feedback

Revision ID: 8b2c6d4e1f30
Revises: 4a7d9c2e6f10
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8b2c6d4e1f30"
down_revision: Union[str, None] = "4a7d9c2e6f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("content_generations", sa.Column("quality_score", sa.Integer(), nullable=True))
    op.add_column("content_generations", sa.Column("quality_evaluator", sa.String(length=100), nullable=True))
    op.add_column("content_generations", sa.Column("quality_disclosure", sa.String(length=100), nullable=True))
    reason = postgresql.ENUM("helpful", "inaccurate", "irrelevant", "unclear", "unsafe", name="answer_feedback_reason", create_type=False)
    reason.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "ai_answer_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("reason", reason, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_ai_answer_feedback_rating"),
        sa.ForeignKeyConstraint(["generation_id"], ["content_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "generation_id", "user_id", name="uq_ai_answer_feedback_actor"),
    )
    op.create_index("ix_ai_answer_feedback_workspace_id", "ai_answer_feedback", ["workspace_id"])
    op.create_index("ix_ai_answer_feedback_generation_id", "ai_answer_feedback", ["generation_id"])


def downgrade() -> None:
    op.drop_table("ai_answer_feedback")
    postgresql.ENUM(name="answer_feedback_reason").drop(op.get_bind(), checkfirst=True)
    op.drop_column("content_generations", "quality_disclosure")
    op.drop_column("content_generations", "quality_evaluator")
    op.drop_column("content_generations", "quality_score")
