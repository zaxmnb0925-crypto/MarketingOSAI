from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / "frontend/app/page.tsx"
PRICING = ROOT / "frontend/app/pricing/page.tsx"
BFF = ROOT / "frontend/app/api/public/plans/route.ts"
SCHEMA = ROOT / "backend/app/schemas/subscription.py"
API = ROOT / "backend/app/api/subscriptions.py"
CSS = ROOT / "frontend/app/globals.css"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_home_targets_chinese_merchants_with_working_public_ctas():
    text = read(HOME)
    assert "所有中文市場商家" in text
    assert 'href="/register"' in text
    assert 'href="/pricing"' in text
    assert 'href="/login"' in text
    assert "redirect(" not in text


def test_current_capabilities_and_roadmap_are_truthfully_separated():
    text = read(HOME)
    current = text[text.index('id="capabilities"'):text.index('id="roadmap"')]
    roadmap = text[text.index('id="roadmap"'):]

    assert "Meta／Facebook" in current
    assert "不宣稱尚未接入的平台" in current
    for planned in (
        "更多廣告與社群平台",
        "即時關鍵字與趨勢訊號",
        "隱私安全的群體智慧",
        "規劃中",
        "研究中",
        "尚未作為目前可用功能銷售",
    ):
        assert planned in roadmap
    assert "跨 Workspace 洩漏" in roadmap


def test_public_pricing_schema_excludes_usage_and_internal_flags():
    schema = read(SCHEMA)
    public = schema[
        schema.index("class PublicPlanResponse"):
        schema.index("class ChangePlanRequest")
    ]
    for forbidden in (
        "monthly_credits",
        "price_twd",
        "is_active",
        "is_public",
        "balance",
        "credits_used",
    ):
        assert forbidden not in public
    assert "list_price_minor" in public
    assert "promotional_price_minor" in public


def test_public_plan_api_and_bff_require_no_browser_token():
    api = read(API)
    handler = api[api.index("async def list_plans("):api.index("@router.get", api.index("async def list_plans("))]
    assert "current_user" not in handler
    assert "get_current_user" not in handler
    assert "PublicPlanResponse" in api

    bff = read(BFF)
    assert '"/api/subscription-plans"' in bff
    assert "cookies" not in bff
    assert "Authorization" not in bff
    assert "export async function GET" in bff


def test_pricing_page_uses_live_public_catalog_without_usage_copy():
    text = read(PRICING)
    assert 'fetch("/api/public/plans"' in text
    assert "promotional_price_minor" in text
    assert "list_price_minor" in text
    assert "TWD" in text
    assert 'href="/register"' in text
    for forbidden in (
        "monthly_credits",
        "credits_used",
        "balance",
        "token usage",
    ):
        assert forbidden not in text


def test_public_pages_have_desktop_and_mobile_layout_contracts():
    css = read(CSS)
    for selector in (
        ".public-nav",
        ".hero-section",
        ".capability-grid",
        ".roadmap-section",
        ".pricing-grid",
        ".site-footer",
        "@media (max-width: 920px)",
        "@media (max-width: 680px)",
    ):
        assert selector in css
