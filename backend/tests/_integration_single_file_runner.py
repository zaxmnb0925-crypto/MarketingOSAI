"""Attest resources, reconstruct targets in memory, then run one test file."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from _integration_execute_flows import assert_same_run_resources
from _integration_execute_orchestration import (
    OrchestrationError,
    SubprocessCommandExecutor,
    safe_subprocess_diagnostic,
)
from _integration_live_attestation import attest_live_resource
from _integration_resource_attestation import (
    reconstruct_database_url, reconstruct_redis_url, safe_diagnostic,
)
from _integration_resource_lifecycle import sanitized_subprocess_environment
from _test_environment_guard import validate_test_environment

ALLOWLIST = {
    "backend/tests/test_publication_reconciliation_postgres_integration.py": False,
    "backend/tests/test_publication_publish_http_integration.py": True,
    "backend/tests/test_publication_publish_normal_mode_integration.py": True,
}

RECONCILIATION_TEST = (
    "backend/tests/"
    "test_publication_reconciliation_postgres_integration.py"
)

RECONCILIATION_SUCCESS_MARKERS = (
    "Real PostgreSQL reconciliation service integration: FULL PASS",
    "Provider/Meta execution invoked: NO",
)


def _pytest_command(relative: str) -> tuple[str, ...]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
    ]

    if relative == RECONCILIATION_TEST:
        command.append("-s")

    command.extend([
        "--disable-warnings",
        "-p",
        "_test_isolation_plugin",
        "-p",
        "_v013h_legacy_target_compat",
        relative.removeprefix("backend/"),
    ])

    return tuple(command)


def _emit_command_diagnostic(
    error: OrchestrationError,
    *,
    child_env: dict[str, str],
) -> None:
    diagnostic = error.diagnostic

    if not diagnostic:
        return

    safe = safe_subprocess_diagnostic(
        diagnostic.get("stdout", ""),
        diagnostic.get("stderr", ""),
        child_env,
    )

    for stream in ("stdout", "stderr"):
        value = safe[stream]

        if not value:
            continue

        label = stream.upper()

        print(
            f"INTEGRATION_CHILD_{label}_BEGIN",
            file=sys.stderr,
        )

        sys.stderr.write(value)

        if not value.endswith("\n"):
            sys.stderr.write("\n")

        print(
            f"INTEGRATION_CHILD_{label}_END",
            file=sys.stderr,
        )


def _run_pytest(
    executor,
    *,
    command: tuple[str, ...],
    child_env: dict[str, str],
    cwd: Path,
    relative: str,
) -> int:
    reconciliation = (
        relative == RECONCILIATION_TEST
    )

    allowed_returncodes = (
        frozenset({5})
        if reconciliation
        else frozenset({0})
    )

    try:
        result = executor.run(
            command,
            env=child_env,
            cwd=cwd,
            allowed_returncodes=allowed_returncodes,
        )
    except OrchestrationError as error:
        _emit_command_diagnostic(
            error,
            child_env=child_env,
        )
        raise

    expected_returncode = (
        5
        if reconciliation
        else 0
    )

    if result.returncode != expected_returncode:
        raise RuntimeError(
            "integration entrypoint returned "
            "unexpected pytest return code"
        )

    if reconciliation:
        lines = result.stdout.splitlines()

        if any(
            lines.count(marker) != 1
            for marker
            in RECONCILIATION_SUCCESS_MARKERS
        ):
            raise RuntimeError(
                "reconciliation semantic success markers "
                "are missing or duplicated"
            )

    return 0


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
    if _required("TEST_RUN_ID") != run_id:
        raise RuntimeError("TEST_RUN_ID and RESOURCE_RUN_ID must match")
    executor = SubprocessCommandExecutor()
    postgres = attest_live_resource(
        sentinel_path=_required("POSTGRES_SENTINEL_PATH"), run_id=run_id,
        resource_type="postgres", image=_required("POSTGRES_IMAGE_REFERENCE"),
        executor=executor,
    )
    child_env = sanitized_subprocess_environment({
        "ENVIRONMENT": "test", "MARKETINGOS_TEST_MODE": "integration",
        "MARKETINGOS_TEST_RESOURCE_SCOPE": "disposable", "TEST_RUN_ID": run_id,
        "SECRET_KEY": "test-only-synthetic-secret",
        "OPENAI_API_KEY": "test-only-not-a-live-key",
        "OAUTH_TOKEN_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "API_DOCS_ENABLED": "false", "REAL_PUBLISH_ENABLED": "false",
        "META_PUBLISH_TRANSPORT_ENABLED": "false",
        "META_PUBLISH_CANARY_MODE_ENABLED": "true",
    })
    child_env["DATABASE_URL"] = reconstruct_database_url(
        postgres, _required("POSTGRES_TEST_PASSWORD")
    )
    child_env.pop("POSTGRES_TEST_PASSWORD", None)
    resources = [postgres]
    if needs_redis:
        redis = attest_live_resource(
            sentinel_path=_required("REDIS_SENTINEL_PATH"), run_id=run_id,
            resource_type="redis", image=_required("REDIS_IMAGE_REFERENCE"),
            executor=executor,
        )
        assert_same_run_resources(postgres.resource_run_id, redis.resource_run_id,
                                  redis_required=True)
        child_env["REDIS_URL"] = reconstruct_redis_url(redis)
        resources.append(redis)
    else:
        assert_same_run_resources(postgres.resource_run_id, None, redis_required=False)
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
    command = _pytest_command(relative)

    return _run_pytest(
        executor,
        command=command,
        child_env=child_env,
        cwd=root / "backend",
        relative=relative,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
