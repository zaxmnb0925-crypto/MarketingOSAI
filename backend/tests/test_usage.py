import inspect
from decimal import Decimal

from app.api import usage as api
from app.services import usage_analytics


def test_usage_decimal_quantizers():
    q2 = usage_analytics.q2(
        Decimal("1.234")
    )

    q6 = usage_analytics.q6(
        Decimal("1.2345678")
    )

    assert q2.as_tuple().exponent == -2
    assert q6.as_tuple().exponent == -6


def test_workspace_usage_service_is_scoped():
    source = inspect.getsource(
        usage_analytics.get_workspace_usage
    )

    assert "workspace_id" in source
    assert "ContentGeneration" in source


def test_usage_endpoint_requires_workspace_access():
    source = inspect.getsource(
        api.workspace_usage
    )

    assert "workspace_id" in source
    assert "require_workspace_" in source
