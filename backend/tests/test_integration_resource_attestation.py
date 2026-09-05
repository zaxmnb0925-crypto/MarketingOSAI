"""No-external unit and source-contract tests for integration attestation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest
import _integration_resource_attestation as attestation

from _integration_resource_attestation import (
    ALEMBIC_TARGET_HEAD, DOCKER_LABELS, ResourceAttestationError,
    authorize_destructive_cleanup, load_sentinel, reconstruct_database_url,
    reconstruct_redis_url, safe_diagnostic, validate_migration_gate,
    validate_candidate_port, validate_runtime_observation,
)

RUN_ID = "r22-0123456789abcdef"
DIGEST = "sha256:" + "a" * 64
CONTAINER_ID = "b" * 64


def evidence(tmp_path: Path, kind: str):
    root = tmp_path / "approved"
    resource_dir = root / RUN_ID / kind
    resource_dir.mkdir(parents=True, mode=0o700)
    (root / RUN_ID).chmod(0o700)
    resource_dir.chmod(0o700)
    if kind == "postgres":
        (resource_dir / "data").mkdir(mode=0o700)
    common = {
        "resource_run_id": RUN_ID, "resource_type": kind,
        "resource_container_id": CONTAINER_ID, "resource_pid": None,
        "resource_image_digest": DIGEST, "resource_host": "127.0.0.1",
        "resource_port": 15432 if kind == "postgres" else 16379,
        "resource_temp_dir": str(resource_dir),
        "database_name": "marketingos_test_r22_0123456789abcdef" if kind == "postgres" else None,
        "database_user": "marketingos_test_0123456789abcdef" if kind == "postgres" else None,
        "redis_db": None if kind == "postgres" else 15,
        "start_time": "2026-08-16T00:00:00Z",
    }
    sentinel = resource_dir / "sentinel.json"
    observation = resource_dir / "observation.json"
    sentinel.write_text(json.dumps(common)); sentinel.chmod(0o600)
    observed = dict(common)
    observed.update({
        "listener_host": "127.0.0.1", "listener_port": common["resource_port"],
        "container_name": f"marketingos-{RUN_ID}-{kind}", "running": True,
        "internal_port": 5432 if kind == "postgres" else 6379,
        "mount_sources": [str(resource_dir / "data")] if kind == "postgres" else [],
        "mount_details": ([{
            "type": "bind", "source": str(resource_dir / "data"),
            "destination": "/var/lib/postgresql/data", "rw": True,
        }] if kind == "postgres" else []),
        "host_tmpfs": (None if kind == "postgres" else {
            "destination": "/data", "rw": True,
            "size_bytes": 67108864, "mode": "0700",
        }),
        "declared_volumes": (["/var/lib/postgresql/data"] if
                             kind == "postgres" else ["/data"]),
        "networks": ["bridge"],
        "docker_labels": {
            DOCKER_LABELS["test"]: "true", DOCKER_LABELS["run"]: RUN_ID,
            DOCKER_LABELS["type"]: kind,
        },
    })
    observation.write_text(json.dumps(observed)); observation.chmod(0o600)
    return root, sentinel, observation


def test_postgres_attestation_reconstructs_only_from_evidence(tmp_path):
    root, sentinel, observation = evidence(tmp_path, "postgres")
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    validate_runtime_observation(attested, observation, approved_root=root)
    url = reconstruct_database_url(attested, "synthetic runtime password")
    assert attested.database_name in url
    assert "synthetic%20runtime%20password" in url


def test_redis_attestation_uses_nonzero_database(tmp_path):
    root, sentinel, observation = evidence(tmp_path, "redis")
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="redis", approved_root=root)
    validate_runtime_observation(attested, observation, approved_root=root)
    assert reconstruct_redis_url(attested).endswith("/15")


def test_redis_persisted_volume_observation_is_rejected(tmp_path):
    root, sentinel, observation = evidence(tmp_path, "redis")
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="redis", approved_root=root)
    data = json.loads(observation.read_text())
    data["mount_sources"] = ["anonymous-id"]
    data["mount_details"] = [{
        "type": "volume", "source": "anonymous-id",
        "destination": "/data", "rw": True,
    }]
    observation.write_text(json.dumps(data)); observation.chmod(0o600)
    with pytest.raises(ResourceAttestationError, match="tmpfs"):
        validate_runtime_observation(attested, observation, approved_root=root)


def test_run_id_mismatch_fails_closed(tmp_path):
    root, sentinel, _ = evidence(tmp_path, "postgres")
    with pytest.raises(ResourceAttestationError):
        load_sentinel(sentinel, expected_run_id="r22-fedcba9876543210",
                      expected_type="postgres", approved_root=root)


def test_insecure_sentinel_mode_fails_closed(tmp_path):
    root, sentinel, _ = evidence(tmp_path, "postgres")
    sentinel.chmod(0o644)
    with pytest.raises(ResourceAttestationError):
        load_sentinel(sentinel, expected_run_id=RUN_ID,
                      expected_type="postgres", approved_root=root)


def test_symlink_sentinel_fails_closed(tmp_path):
    root, sentinel, _ = evidence(tmp_path, "postgres")
    link = sentinel.parent / "linked.json"
    link.symlink_to(sentinel)
    with pytest.raises(ResourceAttestationError):
        load_sentinel(link, expected_run_id=RUN_ID,
                      expected_type="postgres", approved_root=root)


def test_listener_or_label_mismatch_fails_closed(tmp_path):
    root, sentinel, observation = evidence(tmp_path, "postgres")
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    data = json.loads(observation.read_text())
    data["listener_port"] += 1
    observation.write_text(json.dumps(data)); observation.chmod(0o600)
    with pytest.raises(ResourceAttestationError):
        validate_runtime_observation(attested, observation, approved_root=root)


def test_cleanup_and_migration_require_fresh_matching_observation(tmp_path, monkeypatch):
    root, sentinel, observation = evidence(tmp_path, "postgres")
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    authorize_destructive_cleanup(attested, observation, approved_root=root)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("MARKETINGOS_TEST_MODE", "integration")
    monkeypatch.setenv("MARKETINGOS_TEST_RESOURCE_SCOPE", "disposable")
    validate_migration_gate(attested, observation, requested_head=ALEMBIC_TARGET_HEAD,
                            approved_root=root)
    with pytest.raises(ResourceAttestationError):
        validate_migration_gate(attested, observation, requested_head="head",
                                approved_root=root)


def test_candidate_port_rejects_defaults_and_existing_listeners():
    validate_candidate_port(15432, ss_listener_output="", lsof_listener_output="")
    with pytest.raises(ResourceAttestationError):
        validate_candidate_port(5432, ss_listener_output="", lsof_listener_output="")
    with pytest.raises(ResourceAttestationError):
        validate_candidate_port(15432, ss_listener_output="LISTEN", lsof_listener_output="")


def test_safe_diagnostic_excludes_credentials(tmp_path):
    root, sentinel, _ = evidence(tmp_path, "postgres")
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    diagnostic = safe_diagnostic(attested, "allowlisted.py")
    assert not ({"password", "database_url", "redis_url", "secret"} & diagnostic.keys())


def test_runner_source_has_exact_allowlist_and_no_batch_execution():
    root = Path(__file__).resolve().parents[2]
    runner = (root / "scripts/run_backend_integration_cleanroom.sh").read_text()
    expected = {
        "backend/tests/test_p4_ai_accounting_postgres_integration.py",
        "backend/tests/test_p5_platform_admin_postgres_integration.py",
        "backend/tests/test_p5_keyword_intelligence_postgres_integration.py",
        "backend/tests/test_publication_reconciliation_postgres_integration.py",
        "backend/tests/test_publication_publish_http_integration.py",
        "backend/tests/test_publication_publish_normal_mode_integration.py",
    }
    assert all(path in runner for path in expected)
    assert "git add" not in runner and "FLUSHALL" not in runner


def test_operator_owned_metadata_and_atomic_final_paths_pass(tmp_path):
    root, sentinel, observation = evidence(tmp_path, "postgres")
    for path in (sentinel, observation):
        metadata = path.lstat()
        assert stat.S_ISREG(metadata.st_mode)
        assert stat.S_IMODE(metadata.st_mode) == 0o600
        assert (metadata.st_uid, metadata.st_gid) == (os.geteuid(), os.getegid())
    accepted = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    validate_runtime_observation(accepted, observation, approved_root=root)


@pytest.mark.parametrize("identity", [
    lambda: (os.geteuid() + 1, os.getegid()),
    lambda: (os.geteuid(), os.getegid() + 1),
])
def test_sentinel_wrong_operator_uid_or_gid_fails_closed(tmp_path, monkeypatch, identity):
    root, sentinel, _ = evidence(tmp_path, "postgres")
    monkeypatch.setattr(attestation, "lifecycle_operator_identity", identity)
    with pytest.raises(ResourceAttestationError, match="UID|GID"):
        load_sentinel(sentinel, expected_run_id=RUN_ID,
                      expected_type="postgres", approved_root=root)


@pytest.mark.parametrize("identity", [
    lambda: (os.geteuid() + 1, os.getegid()),
    lambda: (os.geteuid(), os.getegid() + 1),
])
def test_observation_wrong_operator_uid_or_gid_fails_closed(tmp_path, monkeypatch, identity):
    root, sentinel, observation = evidence(tmp_path, "postgres")
    accepted = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    monkeypatch.setattr(attestation, "lifecycle_operator_identity", identity)
    with pytest.raises(ResourceAttestationError, match="UID|GID"):
        validate_runtime_observation(accepted, observation, approved_root=root)


def test_root_owned_metadata_is_rejected_for_nonroot_operator():
    if os.geteuid() == 0:
        pytest.skip("contract requires a non-root lifecycle operator")
    root_metadata = SimpleNamespace(
        st_mode=stat.S_IFREG | 0o600, st_uid=0, st_gid=0,
    )
    with pytest.raises(ResourceAttestationError, match="UID"):
        attestation._validate_metadata_stat(
            root_metadata, expected_uid=os.geteuid(), expected_gid=os.getegid(),
        )


def test_missing_and_nonregular_sentinel_fail_closed(tmp_path):
    root, sentinel, _ = evidence(tmp_path, "postgres")
    sentinel.unlink()
    sentinel.mkdir(mode=0o600)
    with pytest.raises(ResourceAttestationError, match="regular"):
        load_sentinel(sentinel, expected_run_id=RUN_ID,
                      expected_type="postgres", approved_root=root)
    sentinel.rmdir()
    with pytest.raises(ResourceAttestationError, match="unavailable"):
        load_sentinel(sentinel, expected_run_id=RUN_ID,
                      expected_type="postgres", approved_root=root)
