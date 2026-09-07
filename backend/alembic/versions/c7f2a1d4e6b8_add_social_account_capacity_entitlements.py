"""Add public social account capacity entitlements."""

from __future__ import annotations

import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7f2a1d4e6b8"
down_revision: Union[str, None] = 'c7d2e9f4a106'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SOCIAL_ACCOUNT_CAPACITIES = {
    "free": 1,
    "pro": 3,
    "business": 10,
}


def upgrade() -> None:
    connection = op.get_bind()

    for plan_code, capacity in (
        SOCIAL_ACCOUNT_CAPACITIES.items()
    ):
        entitlement_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            (
                "marketingos:plan-entitlement:"
                f"{plan_code}:social_accounts.max"
            ),
        )

        connection.execute(
            sa.text(
                """
                INSERT INTO plan_entitlements (
                    id,
                    plan_code,
                    key,
                    value_json,
                    created_at,
                    updated_at
                )
                VALUES (
                    CAST(:id AS UUID),
                    :plan_code,
                    :key,
                    CAST(:value_json AS JSONB),
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (plan_code, key)
                DO UPDATE SET
                    value_json = EXCLUDED.value_json,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "id": str(entitlement_id),
                "plan_code": plan_code,
                "key": "social_accounts.max",
                "value_json": json.dumps(capacity),
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM plan_entitlements
            WHERE key = :key
              AND plan_code IN (
                  'free',
                  'pro',
                  'business'
              )
            """
        ),
        {"key": "social_accounts.max"},
    )
