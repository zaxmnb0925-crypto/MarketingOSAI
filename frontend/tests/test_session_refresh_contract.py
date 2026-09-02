from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_backend_refresh_rotation_locks_consumed_row():
    text = read("backend/app/api/auth.py")
    refresh = text[text.index("async def refresh("):text.index("async def logout(")]
    assert ".with_for_update()" in refresh
    assert refresh.index(".with_for_update()") < refresh.index("stored.revoked = True")


def test_refresh_bff_never_exposes_tokens_and_clears_failed_session():
    text = read("frontend/app/api/auth/refresh/route.ts")
    assert 'cookieStore.get("marketingos_refresh_token")' in text
    assert '"/api/auth/refresh"' in text
    assert "setSessionCookies(" in text
    assert "clearSessionCookies(" in text
    assert "NextResponse.json({ access_token" not in text
    assert "NextResponse.json({ refresh_token" not in text


def test_cookie_contract_is_http_only_scoped_and_migration_safe():
    text = read("frontend/lib/auth-cookies.ts")
    assert "httpOnly: true" in text
    assert 'sameSite: "lax"' in text
    assert 'path: "/api/auth"' in text
    assert '"Path=/"' in text
    assert 'response.headers.append(' in text
    assert "maxAge: 0" in text


def test_session_fetch_is_single_flight_and_retries_once():
    text = read("frontend/lib/session-fetch.ts")
    assert "refreshInFlight" in text
    assert 'fetch("/api/auth/refresh"' in text
    assert "response.status !== 401" in text
    assert text.count("response = await fetch(input, init)") == 2
    assert ".finally(" in text


def test_backend_fetch_has_composed_finite_timeout():
    text = read("frontend/lib/backend.ts")
    assert "BACKEND_TIMEOUT_MS = 15_000" in text
    assert "AbortSignal.timeout(BACKEND_TIMEOUT_MS)" in text
    assert "AbortSignal.any([init.signal, timeoutSignal])" in text


def test_all_authenticated_pages_use_session_fetch():
    for page in ("admin", "brands", "create", "dashboard", "governance", "history"):
        text = read(f"frontend/app/{page}/page.tsx")
        assert 'from "@/lib/session-fetch"' in text
        assert "sessionFetch(" in text
