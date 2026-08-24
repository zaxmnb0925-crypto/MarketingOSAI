"""make workspace subscription commercial expiry nullable

Revision ID: e8f3a1c6d2b4
Revises: d4c8f2a91b70
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f3a1c6d2b4"
down_revision: Union[str, None] = "d4c8f2a91b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EXPIRY_CONSTRAINT = (
    "ck_workspace_subscriptions_commercial_expiry"
)


def upgrade() -> None:
    op.alter_column(
        "workspace_subscriptions",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )

    op.execute(
        """
        UPDATE workspace_subscriptions
        SET expires_at = NULL
        WHERE plan_code = 'free'
        """
    )

    op.create_check_constraint(
        EXPIRY_CONSTRAINT,
        "workspace_subscriptions",
        """
        (
            plan_code = 'free'
            AND expires_at IS NULL
        )
        OR
        (
            plan_code <> 'free'
            AND expires_at IS NOT NULL
        )
        """,
    )


def downgrade() -> None:
    raise RuntimeError(
        "P2 commercial expiry normalization is irreversible; "
        "downgrade would require inventing a commercial expiry "
        "for non-expiring Free subscriptions"
    )
