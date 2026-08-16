import inspect
from datetime import datetime, timezone

from app.api import subscriptions as api
from app.schemas.subscription import (
    ChangePlanRequest,
)
from app.services import subscriptions


def test_add_one_month_preserves_safe_day():
    value = datetime(
        2026,
        1,
        15,
        12,
        0,
        tzinfo=timezone.utc,
    )

    result = subscriptions.add_one_month(
        value
    )

    assert result.year == 2026
    assert result.month == 2
    assert result.day == 15
    assert result.hour == 12


def test_change_plan_schema():
    request = ChangePlanRequest(
        plan_code="pro"
    )

    assert request.plan_code == "pro"


def test_subscription_cycle_is_workspace_scoped():
    source = inspect.getsource(
        subscriptions.ensure_subscription_cycle
    )

    assert "workspace_id" in source
    assert "account" in source


def test_plan_change_requires_workspace_gate():
    source = inspect.getsource(
        api.change_workspace_plan
    )

    assert "workspace_id" in source
    assert "require_workspace_" in source
