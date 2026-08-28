from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PAGE = FRONTEND / "app/admin/page.tsx"
BFF_ROOT = FRONTEND / "app/api/admin"
LOGIN = FRONTEND / "app/login/page.tsx"
CSS = FRONTEND / "app/globals.css"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_page_is_read_only_and_covers_p5b2_surface():
    text = read(PAGE)

    for required in (
        'fetch("/api/admin/me"',
        "/api/admin/workspaces?",
        "/subscription",
        "/payments?",
        "Workspace 搜尋",
        "付款紀錄",
        "paymentStatus",
        "workspacePage",
        "paymentPage",
        'router.replace("/login?next=/admin")',
        "你沒有 Platform Admin 權限",
        "READ ONLY",
    ):
        assert required in text

    assert 'fetch("/api/auth/logout", { method: "POST" })' in text
    assert text.count('method: "POST"') == 1

    for forbidden in (
        'method: "PATCH"',
        'method: "PUT"',
        'method: "DELETE"',
        "/confirm",
        "/suspend",
        "/transition-to-free",
    ):
        assert forbidden not in text


def test_admin_bff_routes_keep_bearer_out_of_browser_code():
    routes = (
        BFF_ROOT / "me/route.ts",
        BFF_ROOT / "workspaces/route.ts",
        BFF_ROOT / "workspaces/[workspaceId]/subscription/route.ts",
        BFF_ROOT / "workspaces/[workspaceId]/payments/route.ts",
    )
    for route in routes:
        text = read(route)
        assert 'cookies } from "next/headers"' in text
        assert '"marketingos_access_token"' in text
        assert "Authorization: `Bearer ${token}`" in text
        assert "export async function GET" in text
        assert "export async function POST" not in text

    page_text = read(PAGE)
    assert "marketingos_access_token" not in page_text
    assert "Authorization" not in page_text


def test_bff_targets_only_existing_platform_admin_read_routes():
    assert '"/api/platform-admin/me"' in read(BFF_ROOT / "me/route.ts")
    assert "/api/platform-admin/workspaces?" in read(
        BFF_ROOT / "workspaces/route.ts"
    )
    assert "/subscription`" in read(
        BFF_ROOT / "workspaces/[workspaceId]/subscription/route.ts"
    )
    assert "/payments?${query.toString()}`" in read(
        BFF_ROOT / "workspaces/[workspaceId]/payments/route.ts"
    )


def test_login_return_and_responsive_styles_are_present():
    login = read(LOGIN)
    css = read(CSS)

    assert 'nextPath === "/admin"' in login
    assert '?next=/admin' not in login
    assert ".admin-shell" in css
    assert ".admin-table-wrap" in css
    assert "@media (max-width: 980px)" in css
    assert "@media (max-width: 720px)" in css
