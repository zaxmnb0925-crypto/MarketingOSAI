"""add commercial schema foundation

Revision ID: d4c8f2a91b70
Revises: 7c91e2f4b6a8
Create Date: 2026-08-24
"""

import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4c8f2a91b70"
down_revision: Union[str, None] = (
    "7c91e2f4b6a8"
)
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


CATALOG = (
    {
        "code": "free",
        "name": "Free",
        "description": "免費體驗方案",
        "is_active": True,
        "is_public": True,
        "sort_order": 10,
        "billing_period": "monthly",
        "currency": "TWD",
        "list_price_minor": 0,
        "promotional_price_minor": None,
        "price_display_note": None,
        "manual_quote_required": False,
        "price_twd": 0,
        "monthly_credits": 20,
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": (
            "專業版 AI 行銷與社群發布方案"
        ),
        "is_active": True,
        "is_public": True,
        "sort_order": 20,
        "billing_period": "monthly",
        "currency": "TWD",
        "list_price_minor": 139900,
        "promotional_price_minor": 99000,
        "price_display_note": (
            "上市早鳥優惠 NT$990/月"
        ),
        "manual_quote_required": False,
        "price_twd": 1399,
        "monthly_credits": 1000,
    },
    {
        "code": "business",
        "name": "Business",
        "description": "企業與團隊進階方案",
        "is_active": True,
        "is_public": True,
        "sort_order": 30,
        "billing_period": "monthly",
        "currency": "TWD",
        "list_price_minor": 399000,
        "promotional_price_minor": None,
        "price_display_note": None,
        "manual_quote_required": False,
        "price_twd": 3990,
        "monthly_credits": 2500,
    },
)


AI_ENTITLEMENTS = {
    "free": {
        "ai_text_generation.enabled": True,
        (
            "ai_text_generation."
            "monthly_allowance"
        ): 3,
        "ai_image_generation.enabled": False,
        "ai_video_generation.enabled": False,
    },
    "pro": {
        "ai_text_generation.enabled": True,
        (
            "ai_text_generation."
            "monthly_allowance"
        ): None,
        "ai_image_generation.enabled": False,
        "ai_video_generation.enabled": False,
    },
    "business": {
        "ai_text_generation.enabled": True,
        (
            "ai_text_generation."
            "monthly_allowance"
        ): None,
        "ai_image_generation.enabled": True,
        "ai_image_generation.quality": (
            "standard"
        ),
        (
            "ai_image_generation."
            "monthly_allowance"
        ): None,
        "ai_video_generation.enabled": True,
        (
            "ai_video_generation."
            "monthly_allowance"
        ): 30,
    },
}


def _seed_catalog() -> None:
    connection = op.get_bind()

    for plan in CATALOG:
        connection.execute(
            sa.text(
                """
                INSERT INTO subscription_plans (
                    code,
                    name,
                    description,
                    price_twd,
                    monthly_credits,
                    is_active,
                    is_public,
                    sort_order,
                    billing_period,
                    currency,
                    list_price_minor,
                    promotional_price_minor,
                    price_display_note,
                    manual_quote_required,
                    created_at,
                    updated_at
                )
                VALUES (
                    :code,
                    :name,
                    :description,
                    :price_twd,
                    :monthly_credits,
                    :is_active,
                    :is_public,
                    :sort_order,
                    :billing_period,
                    :currency,
                    :list_price_minor,
                    :promotional_price_minor,
                    :price_display_note,
                    :manual_quote_required,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    price_twd = EXCLUDED.price_twd,
                    is_active = EXCLUDED.is_active,
                    is_public = EXCLUDED.is_public,
                    sort_order = EXCLUDED.sort_order,
                    billing_period = EXCLUDED.billing_period,
                    currency = EXCLUDED.currency,
                    list_price_minor =
                        EXCLUDED.list_price_minor,
                    promotional_price_minor =
                        EXCLUDED.promotional_price_minor,
                    price_display_note =
                        EXCLUDED.price_display_note,
                    manual_quote_required =
                        EXCLUDED.manual_quote_required,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            plan,
        )

    #
    # Preserve legacy rows and commercial history.
    # Only remove them from the public catalog.
    #
    connection.execute(
        sa.text(
            """
            UPDATE subscription_plans
            SET
                is_public = FALSE,
                updated_at = CURRENT_TIMESTAMP
            WHERE code IN ('starter', 'agency')
            """
        )
    )


def _seed_entitlements() -> None:
    connection = op.get_bind()

    for plan_code, values in (
        AI_ENTITLEMENTS.items()
    ):
        for key, value in values.items():
            entitlement_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                (
                    "marketingos:plan-entitlement:"
                    f"{plan_code}:{key}"
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
                        value_json =
                            EXCLUDED.value_json,
                        updated_at =
                            CURRENT_TIMESTAMP
                    """
                ),
                {
                    "id": str(entitlement_id),
                    "plan_code": plan_code,
                    "key": key,
                    "value_json": json.dumps(
                        value
                    ),
                },
            )


def upgrade() -> None:
    op.add_column(
        "subscription_plans",
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "billing_period",
            sa.String(length=20),
            nullable=False,
            server_default="monthly",
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="TWD",
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "list_price_minor",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "promotional_price_minor",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "price_display_note",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "manual_quote_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            ),
        ),
    )

    subscription_columns = (
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "activated_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "suspended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "cancellation_effective_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default="legacy",
        ),
        sa.Column(
            "entitlement_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "renewal_price_minor",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "billing_currency",
            sa.String(length=3),
            nullable=False,
            server_default="TWD",
        ),
        sa.Column(
            "pricing_source",
            sa.String(length=64),
            nullable=True,
        ),
    )

    for column in subscription_columns:
        op.add_column(
            "workspace_subscriptions",
            column,
        )

    op.create_foreign_key(
        "fk_workspace_subscriptions_activated_by",
        "workspace_subscriptions",
        "users",
        ["activated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE workspace_subscriptions
        SET
            starts_at = cycle_start,
            expires_at = cycle_end,
            activated_at = CASE
                WHEN status = 'active'
                THEN cycle_start
                ELSE NULL
            END
        """
    )

    # Preserve existing commercial terms before the
    # approved public catalog prices are normalized.
    op.execute(
        """
        UPDATE workspace_subscriptions AS ws
        SET
            renewal_price_minor =
                plans.price_twd * 100,
            billing_currency = plans.currency
        FROM subscription_plans AS plans
        WHERE plans.code = ws.plan_code
        """
    )

    op.alter_column(
        "workspace_subscriptions",
        "starts_at",
        existing_type=sa.DateTime(
            timezone=True
        ),
        nullable=False,
    )
    op.alter_column(
        "workspace_subscriptions",
        "expires_at",
        existing_type=sa.DateTime(
            timezone=True
        ),
        nullable=False,
    )

    op.create_check_constraint(
        (
            "ck_workspace_subscriptions_"
            "canonical_status"
        ),
        "workspace_subscriptions",
        (
            "status IN ("
            "'pending_payment', "
            "'active', "
            "'suspended', "
            "'cancelled', "
            "'expired'"
            ")"
        ),
    )

    # Defaults above exist only to backfill rows that
    # predate P1. Future writes use explicit ORM/service
    # values; do not persist migration-only semantics.
    for table_name, column_name in (
        ("subscription_plans", "is_public"),
        ("subscription_plans", "sort_order"),
        ("subscription_plans", "billing_period"),
        ("subscription_plans", "currency"),
        ("subscription_plans", "list_price_minor"),
        (
            "subscription_plans",
            "manual_quote_required",
        ),
        ("subscription_plans", "updated_at"),
        ("workspace_subscriptions", "source"),
        (
            "workspace_subscriptions",
            "entitlement_version",
        ),
        (
            "workspace_subscriptions",
            "renewal_price_minor",
        ),
        (
            "workspace_subscriptions",
            "billing_currency",
        ),
    ):
        op.alter_column(
            table_name,
            column_name,
            server_default=None,
        )

    op.create_table(
        "plan_entitlements",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "plan_code",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "value_json",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
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
        sa.ForeignKeyConstraint(
            ["plan_code"],
            ["subscription_plans.code"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_code",
            "key",
            name=(
                "uq_plan_entitlements_"
                "plan_key"
            ),
        ),
    )
    op.create_index(
        "ix_plan_entitlements_plan_code",
        "plan_entitlements",
        ["plan_code"],
        unique=False,
    )

    op.create_table(
        "platform_admin_memberships",
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            (
                "role IN ("
                "'support', "
                "'billing_admin', "
                "'subscription_admin', "
                "'super_admin'"
                ")"
            ),
            name=(
                "ck_platform_admin_memberships_"
                "role"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "payment_records",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "amount_minor",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "confirmed_by_admin_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "external_reference",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "customer_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "internal_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
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
        sa.CheckConstraint(
            (
                "status IN ("
                "'pending', "
                "'confirmed', "
                "'rejected', "
                "'refunded'"
                ")"
            ),
            name="ck_payment_records_status",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_admin_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            [
                "workspace_subscriptions."
                "workspace_id"
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name=(
                "uq_payment_records_"
                "workspace_idempotency"
            ),
        ),
    )
    op.create_index(
        "ix_payment_records_workspace_id",
        "payment_records",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "admin_subscription_audits",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "payment_record_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "actor_admin_role",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "support_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "before_snapshot_json",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
        ),
        sa.Column(
            "after_snapshot_json",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
        ),
        sa.Column(
            "request_id",
            sa.String(length=128),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_record_id"],
            ["payment_records.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            [
                "workspace_subscriptions."
                "workspace_id"
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        (
            "ix_admin_subscription_audits_"
            "workspace_id"
        ),
        "admin_subscription_audits",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        (
            "ix_admin_subscription_audits_"
            "payment_record_id"
        ),
        "admin_subscription_audits",
        ["payment_record_id"],
        unique=False,
    )

    _seed_catalog()
    _seed_entitlements()

def downgrade() -> None:
    raise RuntimeError(
        "P1 commercial schema foundation is an "
        "irreversible, data-preserving migration; "
        "automated downgrade is prohibited because "
        "commercial, payment, and audit history may "
        "exist and must be preserved"
    )
