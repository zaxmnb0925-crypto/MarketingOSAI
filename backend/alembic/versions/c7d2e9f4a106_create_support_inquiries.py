"""create public support inquiries

Revision ID: c7d2e9f4a106
Revises: b8e4c7d1a902
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "c7d2e9f4a106"
down_revision: str | None = "b8e4c7d1a902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_inquiries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_support_inquiries",
        ),
    )

    op.create_index(
        "ix_support_inquiries_email",
        "support_inquiries",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_support_inquiries_status",
        "support_inquiries",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_support_inquiries_status_created",
        "support_inquiries",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_support_inquiries_status_created",
        table_name="support_inquiries",
    )
    op.drop_index(
        "ix_support_inquiries_status",
        table_name="support_inquiries",
    )
    op.drop_index(
        "ix_support_inquiries_email",
        table_name="support_inquiries",
    )
    op.drop_table("support_inquiries")
