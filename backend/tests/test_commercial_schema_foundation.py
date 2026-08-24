import inspect
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api import platform_admin_access
from app.api import subscriptions as subscription_api
from app.models.commercial import (
    AdminSubscriptionAudit,
    PaymentRecord,
    PLATFORM_ADMIN_ROLES,
)
from app.models.subscription import (
    CANONICAL_SUBSCRIPTION_STATUSES,
    PlanEntitlement,
    SubscriptionPlan,
    WorkspaceSubscription,
)
from app.services.entitlements import (
    EffectiveEntitlements,
    EntitlementUnavailable,
)
from app.services import subscriptions


MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / (
        "d4c8f2a91b70_"
        "add_commercial_schema_foundation.py"
    )
)


def migration_source() -> str:
    return MIGRATION.read_text(
        encoding="utf-8"
    )


def test_catalog_values_are_approved():
    source = migration_source()

    assert '"code": "free"' in source
    assert '"list_price_minor": 0' in source

    assert '"code": "pro"' in source
    assert (
        '"list_price_minor": 139900'
        in source
    )
    assert (
        '"promotional_price_minor": 99000'
        in source
    )

    assert '"code": "business"' in source
    assert (
        '"list_price_minor": 399000'
        in source
    )
    assert "299000" not in source


def test_legacy_monthly_credit_bootstrap_is_transitional():
    source = migration_source()

    assert '"monthly_credits": 20' in source
    assert '"monthly_credits": 1000' in source
    assert '"monthly_credits": 2500' in source

    catalog_upsert = source[
        source.index(
            "INSERT INTO subscription_plans"
        ):source.index(
            "# Preserve legacy rows"
        )
    ]

    assert ":monthly_credits" in catalog_upsert
    assert (
        "monthly_credits = EXCLUDED"
        not in catalog_upsert
    )


def test_product_entitlements_ignore_legacy_credits():
    entitlement_source = inspect.getsource(
        __import__(
            "app.services.entitlements",
            fromlist=["dummy"],
        )
    )
    migration = __import__("runpy").run_path(
        str(MIGRATION)
    )
    catalog = {
        plan["code"]: plan
        for plan in migration["CATALOG"]
    }
    allowance_key = (
        "ai_text_generation.monthly_allowance"
    )

    assert "monthly_credits" not in entitlement_source
    assert catalog["free"]["monthly_credits"] == 20
    assert catalog["pro"]["monthly_credits"] == 1000
    assert (
        catalog["business"]["monthly_credits"]
        == 2500
    )
    assert (
        migration["AI_ENTITLEMENTS"]["free"][
            allowance_key
        ]
        == 3
    )
    assert (
        migration["AI_ENTITLEMENTS"]["pro"][
            allowance_key
        ]
        is None
    )
    assert (
        migration["AI_ENTITLEMENTS"]["business"][
            allowance_key
        ]
        is None
    )


def test_entitlement_seed_uses_deterministic_uuid5():
    source = migration_source()

    assert "uuid.uuid5(" in source
    assert "uuid.NAMESPACE_URL" in source
    assert (
        "marketingos:plan-entitlement:"
        in source
    )
    assert "gen_random_uuid" not in source


def test_existing_terms_precede_catalog_reprice():
    source = migration_source()
    preservation = source.index(
        "plans.price_twd * 100"
    )
    catalog_reprice = source.rindex(
        "_seed_catalog()"
    )

    assert preservation < catalog_reprice
    assert (
        "renewal_price_minor ="
        in source
    )
    assert "plans.list_price_minor" not in source


def test_early_bird_is_not_a_plan():
    source = migration_source()

    assert '"code": "early_bird"' not in source
    assert '"code": "pro_early_bird"' not in source


def test_legacy_plans_are_retained_non_public():
    source = migration_source()

    assert (
        "code IN ('starter', 'agency')"
        in source
    )
    assert "is_public = FALSE" in source
    assert "DELETE FROM subscription_plans" not in source


def test_canonical_subscription_statuses():
    assert set(
        CANONICAL_SUBSCRIPTION_STATUSES
    ) == {
        "pending_payment",
        "active",
        "suspended",
        "cancelled",
        "expired",
    }


def test_workspace_subscription_identity():
    table = WorkspaceSubscription.__table__

    primary_keys = [
        column.name
        for column
        in table.primary_key.columns
    ]

    assert primary_keys == ["workspace_id"]
    assert "id" not in table.columns


def test_commercial_history_uses_workspace_aggregate():
    payment_fks = {
        foreign_key.target_fullname
        for foreign_key
        in PaymentRecord.__table__.foreign_keys
    }

    audit_fks = {
        foreign_key.target_fullname
        for foreign_key
        in AdminSubscriptionAudit.__table__.foreign_keys
    }

    target = (
        "workspace_subscriptions.workspace_id"
    )

    assert target in payment_fks
    assert target in audit_fks
    assert "subscription_id" not in (
        PaymentRecord.__table__.columns
    )
    assert "subscription_id" not in (
        AdminSubscriptionAudit
        .__table__
        .columns
    )


def test_platform_admin_roles_are_separate():
    assert set(PLATFORM_ADMIN_ROLES) == {
        "support",
        "billing_admin",
        "subscription_admin",
        "super_admin",
    }

    source = inspect.getsource(
        platform_admin_access
    )

    assert "MembershipRole" not in source
    assert "PlatformAdminMembership" in source


def test_no_platform_admin_seed():
    source = migration_source()

    assert (
        "INSERT INTO platform_admin_memberships"
        not in source
    )
    assert "@example" not in source


def test_ai_entitlements_are_approved():
    source = migration_source()

    assert (
        '"ai_text_generation.enabled": True'
        in source
    )
    assert (
        '"monthly_allowance"'
        in source
    )
    assert (
        '"ai_image_generation.quality"'
        in source
    )
    assert '"standard"' in source
    assert ": 30" in source

    assert "999999" not in source


def test_plan_entitlement_identity():
    table = PlanEntitlement.__table__

    unique_sets = {
        tuple(
            column.name
            for column
            in constraint.columns
        )
        for constraint in table.constraints
        if constraint.__class__.__name__
        == "UniqueConstraint"
    }

    assert (
        "plan_code",
        "key",
    ) in unique_sets


def test_unknown_entitlement_fails_closed():
    effective = EffectiveEntitlements(
        workspace_id=uuid4(),
        plan_code="free",
        entitlement_version=1,
        values={},
    )

    with pytest.raises(
        EntitlementUnavailable
    ):
        effective.get_required(
            "unknown.capability"
        )


def test_price_is_not_authorization_input():
    source = inspect.getsource(
        __import__(
            "app.services.entitlements",
            fromlist=["dummy"],
        )
    )

    assert "list_price_minor" not in source
    assert "promotional_price_minor" not in source
    assert "price_twd" not in source
    assert "plan_code == \"pro\"" not in source


def test_request_time_catalog_mutation_removed():
    source = inspect.getsource(
        subscriptions.ensure_default_plans
    )

    assert "insert(" not in source
    assert "on_conflict" not in source
    assert "db.add" not in source
    assert "SubscriptionPlan.code" in source


def test_downgrade_is_fail_closed_irreversible():
    source = migration_source()
    downgrade = source[source.index("def downgrade"): ]

    assert "raise RuntimeError(" in downgrade
    assert "irreversible" in downgrade
    assert "automated downgrade is prohibited" in downgrade
    assert "op.drop_table" not in downgrade
    assert "op.drop_column" not in downgrade
    assert "op.drop_constraint" not in downgrade


def test_history_foreign_keys_restrict_deletion():
    payment_workspace_fk = next(
        fk
        for fk in PaymentRecord.__table__.foreign_keys
        if fk.parent.name == "workspace_id"
    )
    audit_workspace_fk = next(
        fk
        for fk in AdminSubscriptionAudit.__table__.foreign_keys
        if fk.parent.name == "workspace_id"
    )
    audit_payment_fk = next(
        fk
        for fk in AdminSubscriptionAudit.__table__.foreign_keys
        if fk.parent.name == "payment_record_id"
    )

    assert payment_workspace_fk.ondelete == "RESTRICT"
    assert audit_workspace_fk.ondelete == "RESTRICT"
    assert audit_payment_fk.ondelete == "RESTRICT"

    source = migration_source()
    assert source.count(
        'ondelete="RESTRICT"'
    ) >= 4


def test_public_catalog_and_selection_require_visibility():
    list_source = inspect.getsource(
        subscription_api.list_plans
    )
    change_source = inspect.getsource(
        subscription_api.change_workspace_plan
    )
    lookup_source = inspect.getsource(
        subscriptions.get_plan
    )

    assert "SubscriptionPlan.is_active" in list_source
    assert "SubscriptionPlan.is_public" in list_source
    assert "not plan.is_active" in change_source
    assert "not plan.is_public" in change_source
    assert "is_public" not in lookup_source


def test_migration_only_defaults_are_removed():
    source = migration_source()

    assert 'server_default="legacy"' in source
    assert (
        '("workspace_subscriptions", "source")'
        in source
    )
    assert "server_default=None" in source
    assert (
        WorkspaceSubscription.__table__
        .columns.source.default.arg
        == "system"
    )


def test_entitlement_resolution_fails_closed():
    source = inspect.getsource(
        __import__(
            "app.services.entitlements",
            fromlist=["dummy"],
        ).resolve_effective_entitlements
    )

    assert "subscription is None" in source
    assert "Subscription is unavailable" in source
    assert "Subscription is not active" in source
    assert "plan_code = \"free\"" not in source
    for status_name in (
        "pending_payment",
        "suspended",
        "cancelled",
        "expired",
    ):
        assert status_name in (
            CANONICAL_SUBSCRIPTION_STATUSES
        )


def test_models_contain_required_catalog_fields():
    columns = (
        SubscriptionPlan.__table__.columns
    )

    for name in (
        "description",
        "is_public",
        "sort_order",
        "billing_period",
        "currency",
        "list_price_minor",
        "promotional_price_minor",
        "price_display_note",
        "manual_quote_required",
        "updated_at",
    ):
        assert name in columns
