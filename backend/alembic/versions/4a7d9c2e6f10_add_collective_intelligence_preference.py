"""add collective intelligence preference

Revision ID: 4a7d9c2e6f10
Revises: 9f31a7c2d4e6
Create Date: 2026-08-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4a7d9c2e6f10"
down_revision: Union[str, None] = "9f31a7c2d4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "collective_intelligence_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "workspaces",
        "collective_intelligence_enabled",
    )
