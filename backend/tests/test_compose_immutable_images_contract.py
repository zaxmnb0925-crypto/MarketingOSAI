import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
OVERRIDE = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")
POSTGRES_DOCKERFILE = (
    ROOT / "postgres" / "Dockerfile"
).read_text(encoding="utf-8")

BACKEND = (
    "marketingos-backend@sha256:"
    "5d5bb6f76d1ee159e38321f48c43aab9bb21b17752563a5d00a6c02dc61ff6c5"
)
FRONTEND = (
    "marketingos-frontend@sha256:"
    "8c05022f639be8b799dedc5c62df411734b9e8545a689a17411149e3eee739ca"
)
POSTGRES = (
    "marketingos-postgres@sha256:"
    "83aa35133ffe747636050bc4ee14d49c9893f3f67e0de5d595ea021345f46b6f"
)
REDIS = (
    "docker.io/library/redis@sha256:"
    "ff02b58f971e7d7d156a1267e283fcbbeee91773b6aa36c49dac28ecfe28eadf"
)


def service_block(text: str, service: str) -> str:
    match = re.search(
        rf"(?ms)^  {re.escape(service)}:\n"
        rf"(.*?)(?=^  [a-zA-Z0-9_-]+:\n|^volumes:|^networks:|\Z)",
        text,
    )
    assert match is not None, f"missing service: {service}"
    return match.group(1)


def image_of(text: str, service: str) -> str:
    block = service_block(text, service)
    match = re.search(r"(?m)^    image: ([^\s]+)$", block)
    assert match is not None, f"missing image: {service}"
    return match.group(1)


def assert_immutable(reference: str) -> None:
    assert re.fullmatch(
        r"[^@\s]+@sha256:[0-9a-f]{64}",
        reference,
    ), reference


def test_four_services_use_exact_immutable_images():
    actual = {
        "db": image_of(MAIN, "db"),
        "redis": image_of(MAIN, "redis"),
        "backend": image_of(MAIN, "backend"),
        "frontend": image_of(OVERRIDE, "frontend"),
    }
    expected = {
        "db": POSTGRES,
        "redis": REDIS,
        "backend": BACKEND,
        "frontend": FRONTEND,
    }
    assert actual == expected
    for reference in actual.values():
        assert_immutable(reference)


def test_application_build_rules_are_removed():
    assert not re.search(r"(?m)^\s+build:\s*$", MAIN)
    assert not re.search(r"(?m)^\s+build:\s*$", OVERRIDE)


def test_local_candidates_forbid_implicit_pull():
    assert "pull_policy: never" in service_block(MAIN, "db")
    assert "pull_policy: never" in service_block(MAIN, "backend")
    assert "pull_policy: never" in service_block(OVERRIDE, "frontend")


def test_postgres_hardening_is_fail_closed():
    assert (
        "FROM docker.io/library/postgres@sha256:"
        "cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
        in POSTGRES_DOCKERFILE
    )
    assert "apk upgrade --no-cache" in POSTGRES_DOCKERFILE
    assert "apk add --no-cache su-exec" in POSTGRES_DOCKERFILE
    assert (
        'exec su-exec postgres "$BASH_SOURCE" "$@"'
        in POSTGRES_DOCKERFILE
    )
    assert "rm -f /usr/local/bin/gosu" in POSTGRES_DOCKERFILE
    assert "test ! -e /usr/local/bin/gosu" in POSTGRES_DOCKERFILE
