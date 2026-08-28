import ast
import inspect
import textwrap
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import subscriptions as api
from app.schemas.subscription import ChangePlanRequest
from app.services import subscriptions


def test_add_one_month_preserves_safe_day():
    value = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    result = subscriptions.add_one_month(value)
    assert result == datetime(2026, 2, 15, 12, 0, tzinfo=timezone.utc)


def test_add_one_month_clamps_month_end_and_leap_year():
    assert subscriptions.add_one_month(
        datetime(2024, 1, 31, tzinfo=timezone.utc)
    ) == datetime(2024, 2, 29, tzinfo=timezone.utc)
    assert subscriptions.add_one_month(
        datetime(2025, 1, 31, tzinfo=timezone.utc)
    ) == datetime(2025, 2, 28, tzinfo=timezone.utc)


def test_change_plan_schema_normalizes_plan_code():
    request = ChangePlanRequest(plan_code=" Pro ")
    assert request.plan_code == "pro"


def test_catalog_is_migration_owned():
    source = inspect.getsource(subscriptions.ensure_default_plans)
    assert "insert(" not in source
    assert "on_conflict" not in source
    assert "SubscriptionCatalogConfigurationError" in source


def test_free_provisioning_is_idempotent_flush_only():
    source = inspect.getsource(subscriptions.provision_free_subscription)
    assert "on_conflict_do_nothing" in source
    assert "expires_at=None" in source
    assert "await db.flush()" in source
    assert "commit(" not in source


def test_cycle_maintenance_cannot_mutate_commercial_authority():
    source = inspect.getsource(subscriptions.ensure_subscription_cycle)
    tree = ast.parse(textwrap.dedent(source))
    assigned_attributes = {
        target.attr
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        for target in (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
        )
        if isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "subscription"
    }
    assert {"cycle_start", "cycle_end"}.issubset(assigned_attributes)
    assert assigned_attributes.isdisjoint({
        "plan_code",
        "status",
        "starts_at",
        "expires_at",
        "renewal_price_minor",
    })
    assert "commit(" not in source


@pytest.mark.asyncio
async def test_customer_plan_change_is_closed(monkeypatch):
    workspace_id = uuid4()
    current_user = SimpleNamespace(id=uuid4())
    db = object()
    membership_checked = False

    async def require_membership(candidate_db, candidate_user, candidate_workspace):
        nonlocal membership_checked
        assert candidate_db is db
        assert candidate_user is current_user
        assert candidate_workspace == workspace_id
        membership_checked = True

    monkeypatch.setattr(api, "require_workspace_membership", require_membership)
    with pytest.raises(HTTPException) as exc:
        await api.change_workspace_plan(
            workspace_id,
            ChangePlanRequest(plan_code="pro"),
            current_user,
            db,
        )
    assert membership_checked is True
    assert exc.value.status_code == 403


def test_customer_subscription_read_does_not_load_credit_account():
    source = inspect.getsource(
        api.get_workspace_subscription
    )

    assert "get_or_create_credit_account" not in source
    assert "monthly_credits" not in source
    assert "credits_granted" not in source
    assert "credits_used" not in source
    assert "lifetime_used" not in source
    assert "balance=" not in source
    assert "commit(" not in source
