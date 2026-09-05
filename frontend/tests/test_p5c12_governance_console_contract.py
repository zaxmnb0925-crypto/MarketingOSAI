from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PAGE = FRONTEND / "app/governance/page.tsx"
CONTRACTS = FRONTEND / "app/governance/_lib/contracts.ts"
PROXY = (
    FRONTEND
    / "app/api/workspaces/[workspaceId]/brands/[brandId]"
    / "quality-policy/[...segments]/route.ts"
)
CSS = FRONTEND / "app/globals.css"
DASHBOARD = FRONTEND / "app/dashboard/page.tsx"
LOGIN = FRONTEND / "app/login/page.tsx"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_governance_console_exposes_complete_existing_p5_workflow():
    page = read(PAGE)

    for required in (
        '"recommendations"',
        '"activations/active"',
        '"effects"',
        '"degradation-recommendations"',
        '"remediations"',
        '"governance-cases"',
        'case "recommendation-decision"',
        'case "activation"',
        'case "activation-rollback"',
        'case "degradation-review"',
        'case "remediation-proposal"',
        'case "remediation-decision"',
        'case "remediation-execution"',
        'case "remediation-closure"',
        'case "case-open"',
        'case "case-closure"',
        "expected_active_activation_id",
        "expected_policy_version",
        "expected_manifest_sha256",
        "idempotency_key",
        "human_confirms_recovery",
        "human_confirms_closure",
        "目前政策",
        "待人工處理",
        "治理證據與結案",
    ):
        assert required in page

    assert 'method: "POST"' in page
    assert 'method: "DELETE"' not in page
    assert "automatic" not in page.lower()


def test_governance_actions_are_explicit_and_role_aware():
    page = read(PAGE)

    assert 'workspace.role !== "viewer"' in page
    assert "EXPLICIT HUMAN ACTION" in page
    assert "確認人工操作" in page
    assert "人工操作理由" in page
    assert "系統不會自動執行" in page
    assert 'role="dialog"' in page
    assert 'aria-modal="true"' in page
    assert "apiError(response.status" in page
    assert "status === 409" in page
    assert "請重新整理後再操作" in page


def test_governance_proxy_keeps_bearer_token_server_side_and_is_allowlisted():
    proxy = read(PROXY)
    page = read(PAGE)

    assert 'cookies } from "next/headers"' in proxy
    assert '"marketingos_access_token"' in proxy
    assert "Authorization: `Bearer ${token}`" in proxy
    assert "ALLOWED_ROOTS" in proxy
    assert "safeSegments" in proxy
    assert 'segments.every((segment) => /^[a-z0-9-]+$/i.test(segment))' in proxy
    assert "/content/quality-policy/${segments.join" in proxy
    assert "export async function GET" in proxy
    assert "export async function POST" in proxy
    assert "export async function DELETE" not in proxy
    assert "marketingos_access_token" not in page
    assert "Authorization" not in page


def test_governance_contract_types_cover_all_operational_layers():
    contracts = read(CONTRACTS)

    for required in (
        "Recommendation",
        "Activation",
        "Effect",
        "Degradation",
        "Remediation",
        "GovernanceCase",
        "GovernanceSnapshot",
        "PendingAction",
    ):
        assert f"export type {required}" in contracts


def test_governance_navigation_login_return_and_responsive_styles():
    dashboard = read(DASHBOARD)
    login = read(LOGIN)
    css = read(CSS)

    assert 'href="/governance"' in dashboard
    assert 'nextPath === "/governance"' in login
    assert ".governance-shell" in css
    assert ".governance-dialog-backdrop" in css
    assert ".governance-permission.write" in css
    assert "@media (max-width: 760px)" in css
