from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = ROOT / "frontend/app/dashboard/page.tsx"
USAGE_ROUTE = (
    ROOT
    / "frontend/app/api/workspaces/[workspaceId]/usage/route.ts"
)
SUBSCRIPTION_ROUTE = (
    ROOT
    / "frontend/app/api/workspaces/[workspaceId]/subscription/route.ts"
)


def test_customer_usage_bff_route_is_absent():
    assert not USAGE_ROUTE.exists()


def test_customer_subscription_bff_uses_http_only_session_boundary():
    text = SUBSCRIPTION_ROUTE.read_text(encoding="utf-8")

    assert 'cookies } from "next/headers"' in text
    assert '"marketingos_access_token"' in text
    assert "Authorization: `Bearer ${token}`" in text
    assert "/api/workspaces/${workspaceId}/subscription" in text


def test_dashboard_does_not_fetch_or_render_customer_usage():
    text = DASHBOARD.read_text(encoding="utf-8")

    forbidden = (
        "/usage",
        "UsageResponse",
        "setUsage",
        "usage.generations",
        "內容生成",
        "總任務",
        "生成活動統計",
    )
    for value in forbidden:
        assert value not in text

    assert "/subscription" in text
    assert "SubscriptionResponse" in text
    assert "plan_name" in text
