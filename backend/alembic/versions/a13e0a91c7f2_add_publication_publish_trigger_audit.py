"""add publication publish trigger audit

Revision ID: a13e0a91c7f2
Revises: b731c8e24d91
Create Date: 2026-08-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a13e0a91c7f2"
down_revision: Union[str, None] = "b731c8e24d91"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.add_column(
        "publications",
        sa.Column(
            "publish_triggered_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    op.add_column(
        "publications",
        sa.Column(
            "publish_triggered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        (
            "fk_publications_"
            "publish_triggered_by_user_id_users"
        ),
        "publications",
        "users",
        ["publish_triggered_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        (
            "ix_publications_"
            "publish_triggered_by_user_id"
        ),
        "publications",
        ["publish_triggered_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        (
            "ix_publications_"
            "publish_triggered_by_user_id"
        ),
        table_name="publications",
    )

    op.drop_constraint(
        (
            "fk_publications_"
            "publish_triggered_by_user_id_users"
        ),
        "publications",
        type_="foreignkey",
    )

    op.drop_column(
        "publications",
        "publish_triggered_at",
    )

    op.drop_column(
        "publications",
        "publish_triggered_by_user_id",
    )
