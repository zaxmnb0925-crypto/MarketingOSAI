import inspect
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import credits, platform_admin_access, subscriptions, usage
from app.api.content import serialize_customer_generation
from app.models.content_generation import ContentGeneration
from app.schemas.content import CustomerContentGenerationResponse
from app.schemas.subscription import (
    CustomerWorkspaceSubscriptionResponse,
    PublicPlanResponse,
)
from app.schemas.usage import WorkspaceUsageResponse
from app.services import ai_credits, usage_analytics

FORBIDDEN_GENERATION = {
    "prompt", "model", "input_tokens", "output_tokens",
    "estimated_cost_usd", "error_message",
}
FORBIDDEN_USAGE = {
    "credits", "tokens", "cost", "profit", "monthly_credits",
    "price_twd", "usage_percent", "balance", "lifetime_used",
    "credits_granted", "credits_used",
}

def recursive_keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(recursive_keys(v) for v in value.values()), set())
    if isinstance(value, list):
        return set().union(*(recursive_keys(v) for v in value), set())
    return set()

def test_customer_generation_schema_and_serializer_hide_internal_fields():
    assert FORBIDDEN_GENERATION.isdisjoint(CustomerContentGenerationResponse.model_fields)
    item = SimpleNamespace(
        id=uuid4(), workspace_id=uuid4(), brand_id=uuid4(), platform="facebook",
        topic="topic", objective=None, status="failed", generated_content=None,
        created_at=ai_credits.utcnow(), updated_at=ai_credits.utcnow(),
        prompt="secret", model="provider-model", input_tokens=1, output_tokens=2,
        estimated_cost_usd="1.0", error_message="provider detail",
    )
    payload = serialize_customer_generation(item).model_dump(mode="json")
    assert FORBIDDEN_GENERATION.isdisjoint(recursive_keys(payload))

def test_customer_subscription_schema_hides_usage_and_accounting():
    schema = CustomerWorkspaceSubscriptionResponse.model_json_schema()
    assert FORBIDDEN_USAGE.isdisjoint(recursive_keys(schema.get("properties", {})))
    assert {"credits", "tokens", "cost", "profit"}.issubset(WorkspaceUsageResponse.model_fields)


def test_public_plan_schema_exposes_price_without_usage_accounting():
    fields = set(PublicPlanResponse.model_fields)
    assert {
        "code",
        "name",
        "description",
        "currency",
        "list_price_minor",
        "promotional_price_minor",
    }.issubset(fields)
    assert FORBIDDEN_USAGE.isdisjoint(fields)
    assert {"is_active", "is_public"}.isdisjoint(fields)

def test_customer_openapi_response_models_are_safe():
    from app.main import app
    document = app.openapi()
    components = document["components"]["schemas"]
    generation = components["CustomerContentGenerationResponse"]["properties"]
    assert FORBIDDEN_GENERATION.isdisjoint(generation)
    customer_subscription = components["CustomerWorkspaceSubscriptionResponse"]["properties"]
    assert FORBIDDEN_USAGE.isdisjoint(recursive_keys(customer_subscription))
    assert "/api/workspaces/{workspace_id}/usage" not in document["paths"]
    assert "/api/platform-admin/workspaces/{workspace_id}/usage" in document["paths"]
    public_plan = components["PublicPlanResponse"]["properties"]
    assert FORBIDDEN_USAGE.isdisjoint(recursive_keys(public_plan))
    assert subscriptions.get_workspace_subscription is not None

def test_internal_accounting_routes_use_platform_authority():
    assert credits.router.prefix.startswith("/api/platform-admin/")
    assert "require_platform_admin_accounting_read" in inspect.getsource(credits.get_credit_ledger)
    assert "require_platform_admin_accounting_read" in inspect.getsource(usage.platform_admin_workspace_usage)
    assert "require_workspace_" not in inspect.getsource(credits.get_credit_ledger)

@pytest.mark.asyncio
async def test_platform_accounting_role_matrix():
    user = SimpleNamespace(id=uuid4())
    allowed = {"support", "billing_admin", "super_admin"}
    for role in ("support", "billing_admin", "subscription_admin", "super_admin"):
        membership = SimpleNamespace(role=role)
        db = SimpleNamespace(execute=lambda query: None)
        class Result:
            def scalar_one_or_none(self): return membership
        async def execute(query): return Result()
        db.execute = execute
        if role in allowed:
            assert await platform_admin_access.require_platform_admin_accounting_read(user, db) is membership
        else:
            with pytest.raises(HTTPException) as exc:
                await platform_admin_access.require_platform_admin_accounting_read(user, db)
            assert exc.value.status_code == 403

def test_internal_models_and_accounting_functions_are_preserved():
    for field in ("prompt", "model", "input_tokens", "output_tokens", "estimated_cost_usd", "error_message"):
        assert field in ContentGeneration.__table__.columns
    assert callable(ai_credits.reserve_credits)
    assert callable(ai_credits.refund_credits)
    assert callable(usage_analytics.get_workspace_usage)
