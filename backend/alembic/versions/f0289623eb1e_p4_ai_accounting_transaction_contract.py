"""P4 AI accounting transaction contract.

Revision ID: f0289623eb1e
Revises: e8f3a1c6d2b4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f0289623eb1e"
down_revision: Union[str, None] = "e8f3a1c6d2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _targeted_duplicate_count() -> int:
    result = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT workspace_id, generation_id
                FROM ai_credit_ledger
                WHERE generation_id IS NOT NULL
                  AND operation = 'content_generation'
                GROUP BY workspace_id, generation_id
                HAVING COUNT(*) > 1
                UNION ALL
                SELECT workspace_id, generation_id
                FROM ai_credit_ledger
                WHERE generation_id IS NOT NULL
                  AND operation IN (
                      'content_policy_refund',
                      'provider_failure_refund'
                  )
                GROUP BY workspace_id, generation_id
                HAVING COUNT(*) > 1
            ) AS targeted_duplicates
            """
        )
    )
    return int(result.scalar_one())


def upgrade() -> None:
    if _targeted_duplicate_count():
        raise RuntimeError(
            "P4 migration blocked: duplicate generation accounting exists"
        )

    op.create_index(
        "uq_ai_credit_ledger_generation_debit",
        "ai_credit_ledger",
        ["workspace_id", "generation_id"],
        unique=True,
        postgresql_where=sa.text(
            "generation_id IS NOT NULL AND "
            "operation = 'content_generation'"
        ),
    )
    op.create_index(
        "uq_ai_credit_ledger_generation_terminal_refund",
        "ai_credit_ledger",
        ["workspace_id", "generation_id"],
        unique=True,
        postgresql_where=sa.text(
            "generation_id IS NOT NULL AND operation IN "
            "('content_policy_refund', 'provider_failure_refund')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_ai_credit_ledger_generation_terminal_refund",
        table_name="ai_credit_ledger",
    )
    op.drop_index(
        "uq_ai_credit_ledger_generation_debit",
        table_name="ai_credit_ledger",
    )
