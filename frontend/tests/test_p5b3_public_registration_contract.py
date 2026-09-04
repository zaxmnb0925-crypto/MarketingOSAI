from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND_AUTH = ROOT / "backend/app/api/auth.py"
SCHEMA = ROOT / "backend/app/schemas/auth.py"
PAGE = ROOT / "frontend/app/register/page.tsx"
BFF = ROOT / "frontend/app/api/auth/register/route.ts"
AUTH_COOKIES = ROOT / "frontend/lib/auth-cookies.ts"
LOGIN = ROOT / "frontend/app/login/page.tsx"
CSS = ROOT / "frontend/app/globals.css"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_registration_backend_is_atomic_and_rate_limited():
    text = read(BACKEND_AUTH)
    register = text[text.index("async def register("):text.index("async def login(")]

    for required in (
        'scope="register"',
        "normalized_login_identifier_hash(",
        "limit=5",
        "window_seconds=3600",
        "provision_free_subscription(",
        "MembershipRole.owner",
        "commit=False",
        "except IntegrityError",
        "status.HTTP_409_CONFLICT",
    ):
        assert required in register

    assert register.count("await db.commit()") == 1
    assert "await db.rollback()" in register


def test_registration_schema_rejects_blank_names():
    text = read(SCHEMA)
    assert '@field_validator("full_name", "workspace_name")' in text
    assert "value = value.strip()" in text
    assert "value must not be blank" in text


def test_registration_bff_keeps_tokens_in_http_only_cookies():
    text = read(BFF)
    cookies = read(AUTH_COOKIES)
    assert '"/api/auth/register"' in text
    assert 'method: "POST"' in text
    assert "setSessionCookies(" in text
    assert '"marketingos_access_token"' in cookies
    assert '"marketingos_refresh_token"' in cookies
    assert "httpOnly: true" in cookies
    assert 'sameSite: "lax"' in cookies
    assert 'process.env.NODE_ENV === "production"' in cookies


def test_public_registration_page_has_required_safe_flow():
    text = read(PAGE)
    for required in (
        'fetch("/api/auth/register"',
        "full_name: fullName.trim()",
        "workspace_name: workspaceName.trim()",
        "password !== confirmation",
        "response.status === 409",
        "response.status === 429",
        'router.replace("/dashboard")',
        "免費方案",
        "不顯示內部 AI 用量或成本資料",
    ):
        assert required in text

    assert "access_token" not in text
    assert "refresh_token" not in text
    assert "Authorization" not in text


def test_login_links_to_registration_and_layout_is_responsive():
    assert 'href="/register"' in read(LOGIN)
    css = read(CSS)
    assert ".register-panel" in css
    assert ".register-field-grid" in css
    assert "@media (max-width: 620px)" in css
