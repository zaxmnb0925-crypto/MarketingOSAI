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
    normalize_docker_observation, postgres_data_dir, require_empty_postgres_data_dir,
    resource_temp_dir, sentinel_payload,
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
        "mount_sources": [str(value.pgdata_dir)] if value.resource_type == "postgres" else [],
        "mount_details": ([{
            "type": "bind", "source": str(value.pgdata_dir),
            "destination": "/var/lib/postgresql/data", "rw": True,
        }] if value.resource_type == "postgres" else [{
            "type": "tmpfs", "source": "", "destination": "/data", "rw": True,
        }]),
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
    assert ("--tmpfs", "/data:rw,size=67108864,mode=0700") == value.argv[
        value.argv.index("--tmpfs"):value.argv.index("--tmpfs") + 2
    ]
    assert value.argv.count("--tmpfs") == 1
    assert not any(option in value.argv for option in ("--mount", "--volume"))
    assert value.argv[-4:] == ("--save", "", "--appendonly", "no")


@pytest.mark.parametrize("mount_details,mount_sources", [
    ([{"type": "volume", "source": "anonymous-id", "destination": "/data", "rw": True}], ["anonymous-id"]),
    ([{"type": "volume", "source": "named-cache", "destination": "/data", "rw": True}], ["named-cache"]),
    ([{"type": "bind", "source": "/tmp/redis-data", "destination": "/data", "rw": True}], ["/tmp/redis-data"]),
    ([{"type": "tmpfs", "source": "", "destination": "/wrong", "rw": True}], []),
    ([{"type": "tmpfs", "source": "", "destination": "/data", "rw": True},
      {"type": "bind", "source": "/tmp/extra", "destination": "/extra", "rw": True}], ["/tmp/extra"]),
    ([{"type": "tmpfs", "source": "", "destination": "/data", "rw": True},
      {"type": "tmpfs", "source": "", "destination": "/data", "rw": True}], []),
])
def test_redis_rejects_noncanonical_storage_observations(
        tmp_path, mount_details, mount_sources):
    value = spec(tmp_path, "redis")
    raw = raw_observation(value)
    raw["mount_details"] = mount_details
    raw["mount_sources"] = mount_sources
    with pytest.raises(ResourceAttestationError, match="mount|storage"):
        normalize_docker_observation(raw, value)


def test_redis_accepts_exact_tmpfs_storage_observation(tmp_path):
    value = spec(tmp_path, "redis")
    observed = normalize_docker_observation(raw_observation(value), value)
    assert observed["mount_sources"] == []
    assert observed["mount_details"] == [{
        "type": "tmpfs", "source": "", "destination": "/data", "rw": True,
    }]


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
    assert "SubprocessCommandExecutor" in text
    assert "provision_resource" in text
    assert "execute_migration" in text
    assert "teardown_resource" in text


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

def test_postgres_resource_root_and_pgdata_are_physically_separate(tmp_path):
    value = spec(tmp_path)
    root = create_resource_directories(RUN_ID, "postgres", tmp_path / "approved")
    assert value.temp_dir == root
    assert value.pgdata_dir == root / "data" == postgres_data_dir(
        RUN_ID, approved_root=tmp_path / "approved")
    assert value.temp_dir != value.pgdata_dir
    assert require_empty_postgres_data_dir(value) == value.pgdata_dir
    mount = f"type=bind,src={value.pgdata_dir},dst=/var/lib/postgresql/data"
    assert mount in value.argv
    assert f"type=bind,src={value.temp_dir},dst=/var/lib/postgresql/data" not in value.argv


@pytest.mark.parametrize("child_kind", ["hidden", "directory"])
def test_pgdata_nonempty_including_hidden_entries_fails_closed(tmp_path, child_kind):
    value = spec(tmp_path)
    create_resource_directories(RUN_ID, "postgres", tmp_path / "approved")
    child = value.pgdata_dir / (".hidden" if child_kind == "hidden" else "child")
    child.write_text("synthetic") if child_kind == "hidden" else child.mkdir()
    with pytest.raises(ResourceAttestationError, match="PGDATA_NOT_EMPTY"):
        require_empty_postgres_data_dir(value)


def test_symlink_pgdata_fails_closed(tmp_path):
    value = spec(tmp_path)
    create_resource_directories(RUN_ID, "postgres", tmp_path / "approved")
    value.pgdata_dir.rmdir()
    outside = tmp_path / "outside-data"; outside.mkdir()
    value.pgdata_dir.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ResourceAttestationError, match="symlink"):
        require_empty_postgres_data_dir(value)


@pytest.mark.parametrize("source", ["resource-root", "sibling", "production"])
def test_unexpected_postgres_mount_sources_fail_closed(tmp_path, source):
    value = spec(tmp_path)
    candidate = {"resource-root": value.temp_dir,
                 "sibling": value.temp_dir.parent / "sibling",
                 "production": Path("/opt/MarketingOSAI")}[source]
    raw = raw_observation(value); raw["mount_sources"] = [str(candidate)]
    with pytest.raises(ResourceAttestationError):
        normalize_docker_observation(raw, value)


def test_metadata_and_atomic_temporary_files_remain_outside_pgdata(tmp_path):
    root = tmp_path / "approved"
    value = spec(tmp_path); create_resource_directories(RUN_ID, "postgres", root)
    payload = {"resource_run_id": RUN_ID, "resource_type": "postgres", "value": "safe"}
    write_secure_json(value.temp_dir / "observation.json", payload, approved_root=root)
    assert (value.temp_dir / "observation.json").is_file()
    assert list(value.pgdata_dir.iterdir()) == []
    with pytest.raises(ResourceAttestationError):
        write_secure_json(value.pgdata_dir / "diagnostic.json", payload, approved_root=root)
    source = Path(__file__).with_name("_integration_resource_lifecycle.py").read_text()
    assert 'temporary = path.parent / f".{path.name}.' in source


def test_pgdata_empty_gate_precedes_docker_create_in_source():
    source = Path(__file__).with_name("_integration_execute_flows.py").read_text()
    assert source.index("require_empty_postgres_data_dir(spec)") < source.index("executor.run(spec.argv")


def test_operator_sentinel_contract_is_privileged_metadata_only():
    policy = (Path(__file__).resolve().parents[2] / "docs/INTEGRATION_RESOURCE_SAFETY.md").read_text()
    assert "sudo -- /usr/bin/stat -Lc" in policy
    operator = policy.split("Operator sentinel metadata contract", 1)[1]
    assert "chmod 755" not in operator and "chmod 777" not in operator
    assert "chown cbemsadmin" not in operator and "cat sentinel" not in operator
