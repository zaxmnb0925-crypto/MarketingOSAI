"""add keyword intelligence foundation

Revision ID: 9f31a7c2d4e6
Revises: f0289623eb1e
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9f31a7c2d4e6"
down_revision: Union[str, None] = "f0289623eb1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "keyword_trend_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(length=200), nullable=False),
        sa.Column(
            "normalized_keyword",
            sa.String(length=200),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=40), nullable=False),
        sa.Column("region", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("momentum", sa.String(length=20), nullable=True),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_keyword_trend_score_range",
        ),
        sa.CheckConstraint(
            "rank IS NULL OR rank > 0",
            name="ck_keyword_trend_rank_positive",
        ),
        sa.CheckConstraint(
            "expires_at > observed_at",
            name="ck_keyword_trend_expiry_after_observation",
        ),
    )
    op.create_index(
        "ix_keyword_trend_workspace_scope",
        "keyword_trend_signals",
        [
            "workspace_id",
            "platform",
            "region",
            "language",
            "observed_at",
        ],
    )
    op.create_index(
        "ix_keyword_trend_workspace_expiry",
        "keyword_trend_signals",
        ["workspace_id", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_keyword_trend_workspace_expiry",
        table_name="keyword_trend_signals",
    )
    op.drop_index(
        "ix_keyword_trend_workspace_scope",
        table_name="keyword_trend_signals",
    )
    op.drop_table("keyword_trend_signals")
