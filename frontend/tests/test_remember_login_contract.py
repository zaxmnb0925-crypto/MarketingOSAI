from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_remember_login_contract():
    schema = read("backend/app/schemas/auth.py")
    login = read("frontend/app/login/page.tsx")
    helper = read("frontend/lib/auth-session.ts")
    login_route = read("frontend/app/api/auth/login/route.ts")
    me_route = read("frontend/app/api/auth/me/route.ts")
    refresh_route = read(
        "frontend/app/api/auth/refresh/route.ts"
    )
    logout_route = read(
        "frontend/app/api/auth/logout/route.ts"
    )

    assert "remember_me: bool = True" in schema
    assert "remember_me: rememberMe" in login
    assert 'autoComplete="username"' in login
    assert 'autoComplete="current-password"' in login

    assert "httpOnly: true" in helper
    assert "REFRESH_TOKEN_COOKIE" in helper
    assert "maxAge: REMEMBER_ME_MAX_AGE" in helper
    assert "applySessionCookies" in login_route

    assert "refreshBackendToken" in me_route
    assert "applySessionCookies" in me_route
    assert "refreshBackendToken" in refresh_route
    assert "applySessionCookies" in refresh_route
    assert "clearSessionCookies" in logout_route
