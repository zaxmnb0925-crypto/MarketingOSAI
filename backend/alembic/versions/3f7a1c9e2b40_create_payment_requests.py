"""create payment requests

Revision ID: 3f7a1c9e2b40
Revises: a1c6e5d9f430
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3f7a1c9e2b40"
down_revision = "a1c6e5d9f430"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_plan_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("customer_note", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("payment_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["payment_record_id"], ["payment_records.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('requested', 'contacted', 'payment_pending', 'fulfilled', 'cancelled')",
            name="ck_payment_requests_status",
        ),
    )
    op.create_index(
        "ix_payment_requests_workspace_id",
        "payment_requests",
        ["workspace_id"],
    )
    op.create_index(
        "ix_payment_requests_payment_record_id",
        "payment_requests",
        ["payment_record_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payment_requests_payment_record_id", table_name="payment_requests")
    op.drop_index("ix_payment_requests_workspace_id", table_name="payment_requests")
    op.drop_table("payment_requests")
