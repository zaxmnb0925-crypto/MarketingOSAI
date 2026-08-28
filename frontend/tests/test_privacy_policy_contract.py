from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

PRIVACY = ROOT / "frontend/app/privacy/page.tsx"
LAYOUT = ROOT / "frontend/app/layout.tsx"


def test_privacy_page_exists():
    assert PRIVACY.is_file()


def test_privacy_page_contains_closed_beta_identity():
    text = PRIVACY.read_text(encoding="utf-8")

    assert "Privacy Policy" in text
    assert "MarketingOS AI" in text
    assert "Closed Beta" in text


def test_privacy_page_contains_required_sections():
    text = PRIVACY.read_text(encoding="utf-8")

    required = (
        "Service identity",
        "Information we collect",
        "Why we process information",
        "AI and service providers",
        "Meta and Facebook integrations",
        "Cookies and session data",
        "Usage, credit, and billing-related data",
        "Data retention",
        "Security",
        "Your choices and rights",
        "Account and data deletion",
        "Third-party services",
        "Changes to this notice",
        "Contact",
    )

    for heading in required:
        assert heading in text


def test_privacy_page_does_not_claim_unproven_legal_metadata():
    text = PRIVACY.read_text(encoding="utf-8")

    forbidden = (
        "Taiwan Company No.",
        "統一編號",
        "registered office",
        "head office address",
    )

    for value in forbidden:
        assert value not in text


def test_global_layout_links_to_privacy_policy():
    text = LAYOUT.read_text(encoding="utf-8")

    assert 'href="/privacy"' in text
    assert "Privacy Policy" in text


def test_privacy_policy_keeps_internal_usage_telemetry_private():
    text = PRIVACY.read_text(encoding="utf-8")

    assert "Customer-facing pages do not expose" in text
    assert "internal accounting telemetry" in text
