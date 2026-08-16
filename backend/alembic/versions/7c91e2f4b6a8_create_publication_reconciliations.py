"""create publication reconciliations

Revision ID: 7c91e2f4b6a8
Revises: a13e0a91c7f2
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c91e2f4b6a8"
down_revision: Union[str, None] = "a13e0a91c7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "publications",
        sa.Column(
            "reconciliation_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "publications",
        "reconciliation_required",
        server_default=None,
    )

    op.create_table(
        "publication_reconciliations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("publication_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("operator_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "decision",
            sa.Enum(
                "confirmed_published",
                "confirmed_failed",
                "remain_unresolved",
                name="publication_reconciliation_decision",
            ),
            nullable=False,
        ),
        sa.Column(
            "publish_attempt_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "provider_post_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "provider_permalink",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "evidence_note",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["publications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operator_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "publication_id",
            "idempotency_key",
            name="uq_publication_reconciliations_publication_idempotency",
        ),
    )

    op.create_index(
        "ix_publication_reconciliations_operator_user_id",
        "publication_reconciliations",
        ["operator_user_id"],
        unique=False,
    )

    op.create_index(
        "ix_publication_reconciliations_publication_created",
        "publication_reconciliations",
        ["publication_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_publication_reconciliations_workspace_created",
        "publication_reconciliations",
        ["workspace_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_publication_reconciliations_workspace_created",
        table_name="publication_reconciliations",
    )
    op.drop_index(
        "ix_publication_reconciliations_publication_created",
        table_name="publication_reconciliations",
    )
    op.drop_index(
        "ix_publication_reconciliations_operator_user_id",
        table_name="publication_reconciliations",
    )
    op.drop_table("publication_reconciliations")

    op.drop_column(
        "publications",
        "reconciliation_required",
    )

    sa.Enum(
        name="publication_reconciliation_decision",
    ).drop(
        op.get_bind(),
        checkfirst=True,
    )
