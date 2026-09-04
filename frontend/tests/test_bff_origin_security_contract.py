from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


MUTATING_ROUTES = (
    "frontend/app/api/auth/refresh/route.ts",
    "frontend/app/api/auth/logout/route.ts",
    "frontend/app/api/workspaces/[workspaceId]/brands/route.ts",
    "frontend/app/api/workspaces/[workspaceId]/brands/[brandId]/route.ts",
    "frontend/app/api/workspaces/[workspaceId]/brands/[brandId]/content/generate/route.ts",
    "frontend/app/api/workspaces/[workspaceId]/brands/[brandId]/quality-policy/[...segments]/route.ts",
)


def test_same_origin_helper_rejects_origin_and_fetch_metadata_mismatch():
    text = read("frontend/lib/same-origin.ts")
    assert '"origin"' in text
    assert '"sec-fetch-site"' in text
    assert '"host"' in text
    assert '"x-forwarded-proto"' in text
    assert "status: 403" in text


def test_proxy_origin_uses_nginx_overwritten_headers():
    text = read("frontend/lib/same-origin.ts")
    assert "expectedOrigin(request" in text
    assert 'normalized !== HTTP_PROTOCOL' in text
    assert 'normalized !== HTTPS_PROTOCOL' in text
    assert 'new URL(`${protocol}//${host}`)' in text

    # Client-controlled X-Forwarded-Host must not be trusted.
    assert 'get("x-forwarded-host")' not in text


def test_malformed_origin_and_host_are_rejected():
    text = read("frontend/lib/same-origin.ts")
    assert "suppliedOrigin(value" in text
    assert 'parsed.pathname !== "/"' in text
    assert "parsed.username" in text
    assert 'host.includes(",")' in text
    assert "/[\\s/\\\\@]/.test(host)" in text
    assert "actual === null" in text
    assert "expected === null" in text


def test_authenticated_mutations_apply_same_origin_gate():
    for path in MUTATING_ROUTES:
        text = read(path)
        assert 'from "@/lib/same-origin"' in text, path
        assert "rejectCrossOrigin(request)" in text, path


def test_browser_security_headers_are_defined():
    text = read("frontend/next.config.mjs")
    for marker in (
        "Content-Security-Policy",
        "frame-ancestors 'none'",
        "X-Content-Type-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ):
        assert marker in text
