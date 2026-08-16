"""Pure safety tests for disposable resource lifecycle tooling."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from _integration_resource_attestation import (
    ResourceAttestationError, load_sentinel, validate_runtime_observation,
)
from _integration_resource_lifecycle import (
    ORCHESTRATION_ORDER, authorize_migration, authorize_teardown,
    build_docker_spec, create_resource_directories, generate_run_id,
    normalize_docker_observation, resource_temp_dir, sentinel_payload,
    sanitized_subprocess_environment, validate_cleanup_path, validate_image_reference, validate_run_id, write_secure_json,
)

RUN_ID = "r22-0123456789abcdef"
PG_IMAGE = "postgres@sha256:" + "a" * 64
REDIS_IMAGE = "redis@sha256:" + "b" * 64
CONTAINER_ID = "c" * 64


def spec(tmp_path: Path, kind: str = "postgres"):
    image = PG_IMAGE if kind == "postgres" else REDIS_IMAGE
    port = 15432 if kind == "postgres" else 16379
    return build_docker_spec(run_id=RUN_ID, resource_type=kind, image=image,
                             port=port, approved_root=tmp_path / "approved")


def raw_observation(value):
    return {
        "container_id": CONTAINER_ID,
        "image_digest": value.image_digest,
        "labels": dict(value.labels),
        "container_name": value.container_name,
        "running": True,
        "published_host": "127.0.0.1",
        "published_port": value.port,
        "internal_port": value.internal_port,
        "started_at": "2026-08-16T00:00:00Z",
        "mount_sources": [str(value.temp_dir)] if value.resource_type == "postgres" else [],
        "networks": ["bridge"],
    }


def evidence(tmp_path: Path, kind: str = "postgres"):
    root = tmp_path / "approved"
    create_resource_directories(RUN_ID, kind, root)
    value = spec(tmp_path, kind)
    observation = normalize_docker_observation(raw_observation(value), value)
    sentinel = value.temp_dir / "sentinel.json"
    observed = value.temp_dir / "observation.json"
    write_secure_json(sentinel, sentinel_payload(observation), approved_root=root)
    write_secure_json(observed, observation, approved_root=root)
    return root, value, sentinel, observed


def test_generated_run_id_is_strict():
    assert validate_run_id(generate_run_id()).startswith("r22-")


@pytest.mark.parametrize("image", ["postgres:16", "redis:7-alpine", "latest"])
def test_tag_only_images_are_rejected(image):
    with pytest.raises(ResourceAttestationError):
        validate_image_reference(image)


def test_malformed_digest_is_rejected():
    with pytest.raises(ResourceAttestationError):
        validate_image_reference("postgres@sha256:abc")


def test_postgres_spec_is_loopback_digest_pinned_and_secret_safe(tmp_path):
    value = spec(tmp_path)
    assert "127.0.0.1:15432:5432" in value.argv
    assert "POSTGRES_PASSWORD" in value.argv
    assert not any("password=" in item.lower() for item in value.argv)
    assert value.image == PG_IMAGE and value.database_name.startswith("marketingos_test_r22_")


def test_redis_spec_disables_persistence_and_uses_nonzero_db(tmp_path):
    value = spec(tmp_path, "redis")
    assert value.redis_db == 15
    assert value.argv[-4:] == ("--save", "", "--appendonly", "no")


def test_default_service_ports_are_rejected(tmp_path):
    with pytest.raises(ResourceAttestationError):
        build_docker_spec(run_id=RUN_ID, resource_type="postgres", image=PG_IMAGE,
                          port=5432, approved_root=tmp_path / "approved")
    with pytest.raises(ResourceAttestationError):
        build_docker_spec(run_id=RUN_ID, resource_type="redis", image=REDIS_IMAGE,
                          port=6379, approved_root=tmp_path / "approved")


def test_redis_db_zero_is_rejected(tmp_path):
    with pytest.raises(ResourceAttestationError):
        build_docker_spec(run_id=RUN_ID, resource_type="redis", image=REDIS_IMAGE,
                          port=16379, redis_db=0, approved_root=tmp_path / "approved")


@pytest.mark.parametrize("field", ["labels", "container_id", "image_digest",
                                    "published_host", "published_port", "internal_port"])
def test_observation_identity_mismatch_is_rejected(tmp_path, field):
    value = spec(tmp_path)
    raw = raw_observation(value)
    replacements = {
        "labels": {}, "container_id": "short", "image_digest": "sha256:" + "d" * 64,
        "published_host": "0.0.0.0", "published_port": 15433, "internal_port": 5433,
    }
    raw[field] = replacements[field]
    with pytest.raises(ResourceAttestationError):
        normalize_docker_observation(raw, value)


def test_missing_observation_field_is_rejected(tmp_path):
    value = spec(tmp_path)
    raw = raw_observation(value)
    raw.pop("labels")
    with pytest.raises(ResourceAttestationError):
        normalize_docker_observation(raw, value)


def test_production_mount_and_network_are_rejected(tmp_path):
    value = spec(tmp_path)
    raw = raw_observation(value)
    raw["mount_sources"] = ["/opt/MarketingOSAI"]
    with pytest.raises(ResourceAttestationError):
        normalize_docker_observation(raw, value)
    raw = raw_observation(value); raw["networks"] = ["marketingos-production"]
    with pytest.raises(ResourceAttestationError):
        normalize_docker_observation(raw, value)


def test_secure_evidence_roundtrip_and_modes(tmp_path):
    root, value, sentinel, observed = evidence(tmp_path)
    assert sentinel.stat().st_mode & 0o777 == 0o600
    attested = load_sentinel(sentinel, expected_run_id=RUN_ID,
                             expected_type="postgres", approved_root=root)
    validate_runtime_observation(attested, observed, approved_root=root)
    assert attested.resource_container_id == CONTAINER_ID


def test_secret_field_is_rejected_before_write(tmp_path):
    root = tmp_path / "approved"
    target = create_resource_directories(RUN_ID, "postgres", root)
    with pytest.raises(ResourceAttestationError):
        write_secure_json(target / "bad.json", {
            "resource_run_id": RUN_ID, "resource_type": "postgres", "password": "synthetic"
        }, approved_root=root)


def test_credential_url_value_is_rejected_before_write(tmp_path):
    root = tmp_path / "approved"
    target = create_resource_directories(RUN_ID, "postgres", root)
    with pytest.raises(ResourceAttestationError):
        write_secure_json(target / "bad.json", {
            "resource_run_id": RUN_ID, "resource_type": "postgres",
            "value": "postgresql://user:synthetic@example.invalid/test",
        }, approved_root=root)


def test_symlink_and_outside_approved_root_are_rejected(tmp_path):
    root = tmp_path / "approved"
    other = tmp_path / "other"; other.mkdir()
    link = root
    link.symlink_to(other, target_is_directory=True)
    with pytest.raises(ResourceAttestationError):
        resource_temp_dir(RUN_ID, "postgres", link)
    with pytest.raises(ResourceAttestationError):
        resource_temp_dir(RUN_ID, "postgres", Path("/home/test-root"))


def test_intermediate_symlink_root_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ResourceAttestationError):
        resource_temp_dir(RUN_ID, "postgres", link / "nested")


def test_wrong_database_name_in_sentinel_is_rejected(tmp_path):
    root, value, sentinel, _ = evidence(tmp_path)
    data = json.loads(sentinel.read_text()); sentinel.unlink()
    data["database_name"] = "marketingos"
    write_secure_json(sentinel, data, approved_root=root)
    with pytest.raises(ResourceAttestationError):
        load_sentinel(sentinel, expected_run_id=RUN_ID,
                      expected_type="postgres", approved_root=root)


def test_teardown_requires_exact_fresh_observation(tmp_path):
    root, value, sentinel, observed = evidence(tmp_path)
    commands = authorize_teardown(sentinel_path=sentinel, observation_path=observed,
                                  run_id=RUN_ID, resource_type="postgres", approved_root=root)
    assert all(command[-1] == CONTAINER_ID for command in commands)
    assert validate_cleanup_path(value.temp_dir, run_id=RUN_ID,
                                 resource_type="postgres", approved_root=root) == value.temp_dir
    data = json.loads(observed.read_text()); observed.unlink(); data["listener_port"] += 1
    write_secure_json(observed, data, approved_root=root)
    with pytest.raises(ResourceAttestationError):
        authorize_teardown(sentinel_path=sentinel, observation_path=observed,
                           run_id=RUN_ID, resource_type="postgres", approved_root=root)


def test_migration_requires_attestation_environment_and_exact_head(tmp_path, monkeypatch):
    root, value, sentinel, observed = evidence(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("MARKETINGOS_TEST_MODE", "integration")
    monkeypatch.setenv("MARKETINGOS_TEST_RESOURCE_SCOPE", "disposable")
    command = authorize_migration(sentinel_path=sentinel, observation_path=observed,
                                  run_id=RUN_ID, runtime_password="runtime-only",
                                  approved_root=root)
    assert command[-1] == "7c91e2f4b6a8" and "runtime-only" not in command


def test_migration_without_required_environment_is_rejected(tmp_path, monkeypatch):
    root, value, sentinel, observed = evidence(tmp_path)
    monkeypatch.delenv("MARKETINGOS_TEST_RESOURCE_SCOPE", raising=False)
    with pytest.raises(ResourceAttestationError):
        authorize_migration(sentinel_path=sentinel, observation_path=observed,
                            run_id=RUN_ID, runtime_password="runtime-only",
                            approved_root=root)


def test_orchestration_is_ordered_and_has_no_run_all():
    assert ORCHESTRATION_ORDER == (
        "provision", "observe", "attest", "migrate-postgres",
        "single-integration-file", "verify", "exact-teardown",
    )
    assert "run-all-integration" not in ORCHESTRATION_ORDER


def test_cli_sources_default_dry_run_and_avoid_unsafe_execution():
    root = Path(__file__).resolve().parents[2]
    names = [
        "provision_integration_resources_cleanroom.py",
        "validate_integration_docker_observation_cleanroom.py",
        "run_integration_migration_cleanroom.py",
        "teardown_integration_resources_cleanroom.py",
    ]
    text = "\n".join((root / "scripts" / name).read_text() for name in names)
    for unsafe in ("shell=True", "os.system", "eval(", "docker system prune",
                   "docker container prune", "pkill", "killall"):
        assert unsafe not in text
    assert "STOP: Docker execution is not implemented or authorized" in text
    assert "STOP: Alembic execution is not implemented or authorized" in text


def test_subprocess_environment_is_allowlisted_and_scrubbed(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-inherit")
    child = sanitized_subprocess_environment({"POSTGRES_PASSWORD": "runtime-only"})
    assert "AWS_SECRET_ACCESS_KEY" not in child
    assert child["POSTGRES_PASSWORD"] == "runtime-only"
    with pytest.raises(ResourceAttestationError):
        sanitized_subprocess_environment({"UNREVIEWED_VARIABLE": "value"})


def test_inherited_resource_urls_are_discarded_by_integration_entrypoint():
    root = Path(__file__).resolve().parents[2]
    runner = (root / "scripts/run_backend_integration_cleanroom.sh").read_text()
    assert "unset DATABASE_URL REDIS_URL" in runner
