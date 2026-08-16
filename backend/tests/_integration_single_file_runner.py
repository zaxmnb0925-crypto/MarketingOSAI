"""Attest resources, reconstruct targets in memory, then run one test file."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from _integration_resource_attestation import (
    load_sentinel, reconstruct_database_url, reconstruct_redis_url,
    safe_diagnostic, validate_runtime_observation,
)
from _test_environment_guard import validate_test_environment

ALLOWLIST = {
    "backend/tests/test_publication_reconciliation_postgres_integration.py": False,
    "backend/tests/test_publication_publish_http_integration.py": True,
    "backend/tests/test_publication_publish_normal_mode_integration.py": True,
}


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"required runtime input is missing: {name}")
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"true", "false"}:
        raise RuntimeError("single-file runner arguments are invalid")
    root = Path(__file__).resolve().parents[2]
    requested = Path(argv[0]).resolve()
    try:
        relative = requested.relative_to(root).as_posix()
    except ValueError as exc:
        raise RuntimeError("integration test is outside repository") from exc
    needs_redis = argv[1] == "true"
    if relative not in ALLOWLIST or ALLOWLIST[relative] is not needs_redis:
        raise RuntimeError("integration test/resource mapping is not allowlisted")

    run_id = _required("RESOURCE_RUN_ID")
    postgres = load_sentinel(_required("POSTGRES_SENTINEL_PATH"),
                             expected_run_id=run_id, expected_type="postgres")
    validate_runtime_observation(postgres, _required("POSTGRES_OBSERVATION_PATH"))
    child_env = dict(os.environ)
    child_env["DATABASE_URL"] = reconstruct_database_url(
        postgres, _required("POSTGRES_TEST_PASSWORD")
    )
    child_env.pop("POSTGRES_TEST_PASSWORD", None)
    resources = [postgres]
    if needs_redis:
        redis = load_sentinel(_required("REDIS_SENTINEL_PATH"),
                              expected_run_id=run_id, expected_type="redis")
        validate_runtime_observation(redis, _required("REDIS_OBSERVATION_PATH"))
        child_env["REDIS_URL"] = reconstruct_redis_url(redis)
        resources.append(redis)
    else:
        child_env["REDIS_URL"] = "redis://127.0.0.1:1/15"

    previous = dict(os.environ)
    try:
        os.environ.clear(); os.environ.update(child_env)
        validate_test_environment()
    finally:
        os.environ.clear(); os.environ.update(previous)
    for resource in resources:
        fields = safe_diagnostic(resource, relative)
        print("INTEGRATION_RESOURCE_ATTESTATION=PASS " + " ".join(
            f"{key}={value}" for key, value in fields.items()
        ))
    command = [sys.executable, "-m", "pytest", "-q", "--disable-warnings",
               "-p", "_test_isolation_plugin", "-p", "_v013h_legacy_target_compat",
               relative.removeprefix("backend/")]
    return subprocess.run(command, env=child_env, cwd=root / "backend", check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
