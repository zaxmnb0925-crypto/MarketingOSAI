"""Additional fake-only rollback and teardown safety cases for B5F."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import _integration_execute_flows as flows
import _integration_resource_attestation as attestation
from _integration_docker_command import docker_subcommand
from _integration_execute_flows import (
    provision_resource, remove_empty_run_directory, teardown_resource,
)
from _integration_execute_orchestration import CommandResult, FailureClass, OrchestrationError
from _integration_resource_lifecycle import (
    build_docker_spec, create_resource_directories, normalize_docker_observation,
    run_temp_dir, sentinel_payload, validate_run_cleanup_path, write_secure_json,
)
from _integration_execute_orchestration import parse_restricted_docker_observation

RUN_ID = "r22-0123456789abcdef"
IMAGE = "docker.io/library/postgres@sha256:" + "a" * 64
CID = "c" * 64


def spec(tmp_path):
    return build_docker_spec(run_id=RUN_ID, resource_type="postgres", image=IMAGE,
                             port=15432, approved_root=tmp_path / "approved")


def redis_spec(tmp_path):
    return build_docker_spec(
        run_id=RUN_ID, resource_type="redis",
        image="docker.io/library/redis@sha256:" + "b" * 64,
        port=16379, approved_root=tmp_path / "approved",
    )


def inspected(value, *, running=True, labels=None, mounts=None, host_tmpfs=None):
    values = [CID, "/" + value.container_name, value.image,
              dict(value.labels) if labels is None else labels, running,
              "2026-08-16T00:00:00Z", "bridge",
              {f"{value.internal_port}/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(value.port)}]},
              (([{"Type": "bind", "Source": str(value.pgdata_dir),
                  "Destination": "/var/lib/postgresql/data", "RW": True}]
                if value.resource_type == "postgres" else [])
               if mounts is None else mounts),
              (({} if value.resource_type == "postgres" else
                {"/data": "rw,size=67108864,mode=0700"})
               if host_tmpfs is None else host_tmpfs),
              ({"/var/lib/postgresql/data": {}} if value.resource_type == "postgres"
               else {"/data": {}})]
    return "\n".join(json.dumps(item) for item in values)


class Fake:
    def __init__(self, value, *, start_fails=False, port_closes=True):
        self.value, self.start_fails, self.port_closes = value, start_fails, port_closes
        self.calls, self.ss_count, self.removed = [], 0, False

    def run(self, argv, **kwargs):
        argv = tuple(argv); self.calls.append((argv, kwargs))
        if docker_subcommand(argv) == "ps": return CommandResult(0, "")
        if argv[0].endswith("/ss"):
            self.ss_count += 1
            open_now = self.ss_count > 1 and not (self.removed and self.port_closes)
            return CommandResult(0, f"LISTEN 0 1 127.0.0.1:{self.value.port} 0.0.0.0:*\n" if open_now else "")
        if argv[0].endswith("/lsof"):
            open_now = self.ss_count > 1 and not (self.removed and self.port_closes)
            return CommandResult(0 if open_now else 1,
                                 f"docker-proxy TCP 127.0.0.1:{self.value.port} (LISTEN)" if open_now else "")
        if argv == self.value.argv: return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "start":
            if self.start_fails: raise RuntimeError("synthetic start failure")
            return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "inspect":
            if self.removed: return CommandResult(1, "")
            return CommandResult(0, inspected(self.value, running=not self.start_fails))
        if docker_subcommand(argv) == "stop": return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "rm": self.removed = True; return CommandResult(0, CID + "\n")
        raise AssertionError(argv)


def evidence(tmp_path):
    value = spec(tmp_path); create_resource_directories(RUN_ID, "postgres", tmp_path / "approved")
    observation = normalize_docker_observation(
        parse_restricted_docker_observation(inspected(value), value), value)
    sentinel = value.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation), approved_root=tmp_path / "approved")
    return value, sentinel


def test_redis_teardown_requires_fresh_exact_tmpfs_identity(tmp_path):
    value = redis_spec(tmp_path)
    create_resource_directories(RUN_ID, "redis", tmp_path / "approved")
    observation = normalize_docker_observation(
        parse_restricted_docker_observation(inspected(value), value), value)
    sentinel = value.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation),
                      approved_root=tmp_path / "approved")
    fake = Fake(value); fake.ss_count = 1
    result = teardown_resource(
        sentinel_path=sentinel, run_id=RUN_ID, resource_type="redis",
        image=value.image, executor=fake, approved_root=tmp_path / "approved")
    assert result["state"] == "COMPLETE"
    assert [argv[3:] for argv, _ in fake.calls if docker_subcommand(argv) in {"stop", "rm"}] == [
        ("stop", CID), ("rm", CID)]


def test_redis_volume_observation_never_authorizes_teardown(tmp_path):
    value = redis_spec(tmp_path)
    create_resource_directories(RUN_ID, "redis", tmp_path / "approved")
    observation = normalize_docker_observation(
        parse_restricted_docker_observation(inspected(value), value), value)
    sentinel = value.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation),
                      approved_root=tmp_path / "approved")
    fake = Fake(value); fake.ss_count = 1
    original = fake.run
    def volume_instead_of_tmpfs(argv, **kwargs):
        if docker_subcommand(tuple(argv)) == "inspect" and not fake.removed:
            fake.calls.append((tuple(argv), kwargs))
            mounts = [{"Type": "volume", "Source": "anonymous-id",
                       "Destination": "/data", "RW": True}]
            return CommandResult(0, inspected(value, mounts=mounts))
        return original(argv, **kwargs)
    fake.run = volume_instead_of_tmpfs
    with pytest.raises(Exception):
        teardown_resource(
            sentinel_path=sentinel, run_id=RUN_ID, resource_type="redis",
            image=value.image, executor=fake, approved_root=tmp_path / "approved")
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)


def test_redis_tmpfs_drift_never_authorizes_teardown(tmp_path):
    value = redis_spec(tmp_path)
    create_resource_directories(RUN_ID, "redis", tmp_path / "approved")
    observation = normalize_docker_observation(
        parse_restricted_docker_observation(inspected(value), value), value)
    sentinel = value.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation),
                      approved_root=tmp_path / "approved")
    fake = Fake(value); fake.ss_count = 1
    original = fake.run
    def drift(argv, **kwargs):
        if docker_subcommand(tuple(argv)) == "inspect" and not fake.removed:
            fake.calls.append((tuple(argv), kwargs))
            return CommandResult(0, inspected(
                value, host_tmpfs={"/data": "rw,size=1024,mode=0700"}))
        return original(argv, **kwargs)
    fake.run = drift
    with pytest.raises(Exception):
        teardown_resource(
            sentinel_path=sentinel, run_id=RUN_ID, resource_type="redis",
            image=value.image, executor=fake, approved_root=tmp_path / "approved")
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)


def test_start_failure_preserves_exact_resource_for_review(tmp_path):
    value = spec(tmp_path); fake = Fake(value, start_fails=True)
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake,
                           approved_root=tmp_path / "approved")
    assert error.value.category is FailureClass.PROVISION_FAILED_REVIEW_REQUIRED
    assert error.value.original_category is FailureClass.START_FAILED
    assert error.value.ownership_boundary == "POST_CREATE_PRESERVE"
    assert error.value.resource_preserved is True
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)
    assert value.temp_dir.exists()


def test_sentinel_write_failure_preserves_resource_for_review(tmp_path, monkeypatch):
    value = spec(tmp_path); fake = Fake(value)
    real_write = flows.write_secure_json; count = {"value": 0}
    def fail_second(*args, **kwargs):
        count["value"] += 1
        if count["value"] == 2: raise OSError("synthetic write failure")
        return real_write(*args, **kwargs)
    monkeypatch.setattr(flows, "write_secure_json", fail_second)
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake,
                           approved_root=tmp_path / "approved")
    assert error.value.category is FailureClass.PROVISION_FAILED_REVIEW_REQUIRED
    assert error.value.original_category is FailureClass.SENTINEL_WRITE_FAILED
    assert error.value.ownership_boundary == "POST_CREATE_PRESERVE"
    assert error.value.resource_preserved is True
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)
    assert value.temp_dir.exists()


def assert_review_required(error, original_category):
    assert error.value.category is FailureClass.PROVISION_FAILED_REVIEW_REQUIRED
    assert error.value.original_category is original_category
    assert error.value.ownership_boundary == "POST_CREATE_PRESERVE"
    assert error.value.resource_preserved is True


def test_initial_observation_failure_preserves_resource(tmp_path):
    value = spec(tmp_path); fake = Fake(value)
    original = fake.run
    def invalid_observation(argv, **kwargs):
        if docker_subcommand(tuple(argv)) == "inspect":
            fake.calls.append((tuple(argv), kwargs))
            return CommandResult(0, "malformed")
        return original(argv, **kwargs)
    fake.run = invalid_observation
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake, approved_root=tmp_path / "approved")
    assert_review_required(error, FailureClass.DOCKER_OBSERVATION_FAILED)
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)
    assert value.temp_dir.exists()


def test_redis_storage_attestation_failure_preserves_resource(tmp_path):
    value = redis_spec(tmp_path); fake = Fake(value)
    original = fake.run
    def invalid_storage(argv, **kwargs):
        if docker_subcommand(tuple(argv)) == "inspect":
            fake.calls.append((tuple(argv), kwargs))
            return CommandResult(0, inspected(
                value, host_tmpfs={"/data": "rw,size=1024,mode=0700"}))
        return original(argv, **kwargs)
    fake.run = invalid_storage
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake, approved_root=tmp_path / "approved")
    assert_review_required(error, FailureClass.RESOURCE_IDENTITY_MISMATCH)
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)
    assert value.temp_dir.exists()


def test_stability_drift_preserves_resource(tmp_path):
    value = spec(tmp_path); fake = Fake(value); inspect_count = 0
    original = fake.run
    def drift(argv, **kwargs):
        nonlocal inspect_count
        if docker_subcommand(tuple(argv)) == "inspect":
            inspect_count += 1
            fake.calls.append((tuple(argv), kwargs))
            started = ("2026-08-16T00:00:01Z" if inspect_count > 1 else
                       "2026-08-16T00:00:00Z")
            return CommandResult(0, inspected(value).replace(
                json.dumps("2026-08-16T00:00:00Z"), json.dumps(started), 1))
        return original(argv, **kwargs)
    fake.run = drift
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake, approved_root=tmp_path / "approved")
    assert_review_required(error, FailureClass.LIFECYCLE_STABILITY_FAILED)
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)
    assert value.temp_dir.exists()


def test_post_sentinel_failure_preserves_container_and_metadata(tmp_path, monkeypatch):
    value = spec(tmp_path); fake = Fake(value); sentinel_written = False
    real_write = flows.write_secure_json
    def tracked_write(path, payload, **kwargs):
        nonlocal sentinel_written
        real_write(path, payload, **kwargs)
        if path.name == "sentinel.json":
            sentinel_written = True
    original = fake.run
    def post_sentinel_drift(argv, **kwargs):
        if docker_subcommand(tuple(argv)) == "inspect" and sentinel_written:
            fake.calls.append((tuple(argv), kwargs))
            return CommandResult(0, inspected(value, running=False))
        return original(argv, **kwargs)
    monkeypatch.setattr(flows, "write_secure_json", tracked_write)
    fake.run = post_sentinel_drift
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake, approved_root=tmp_path / "approved")
    assert_review_required(error, FailureClass.RESOURCE_IDENTITY_MISMATCH)
    assert sentinel_written
    assert (value.temp_dir / "sentinel.json").is_file()
    assert (value.temp_dir / "observation.json").is_file()
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)


def test_teardown_uses_fresh_observation_exact_id_and_closes_port(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value); fake.ss_count = 1
    result = teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                               resource_type="postgres", image=IMAGE,
                               executor=fake, approved_root=tmp_path / "approved")
    assert result == {
        "state": "COMPLETE", "container_id": CID,
        "resource_path_absent": True, "run_directory_absent": True,
        "run_directory_retained_for_sibling": False,
    }
    assert (tmp_path / "approved").is_dir()
    assert not run_temp_dir(RUN_ID, tmp_path / "approved").exists()
    assert [argv[3:] for argv, _ in fake.calls if docker_subcommand(argv) in {"stop", "rm"}] == [("stop", CID), ("rm", CID)]
    assert fake.ss_count == 3


def test_redis_teardown_removes_empty_run_directory_and_preserves_root(tmp_path):
    value = redis_spec(tmp_path)
    root = tmp_path / "approved"
    create_resource_directories(RUN_ID, "redis", root)
    observation = normalize_docker_observation(
        parse_restricted_docker_observation(inspected(value), value), value)
    sentinel = value.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation), approved_root=root)
    fake = Fake(value); fake.ss_count = 1
    result = teardown_resource(
        sentinel_path=sentinel, run_id=RUN_ID, resource_type="redis",
        image=value.image, executor=fake, approved_root=root)
    assert root.is_dir()
    assert not run_temp_dir(RUN_ID, root).exists()
    assert not value.temp_dir.exists() and not sentinel.exists()
    assert result["resource_path_absent"] is True
    assert result["run_directory_absent"] is True
    assert result["run_directory_retained_for_sibling"] is False


def test_same_run_sibling_teardown_reports_parent_retained(tmp_path):
    root = tmp_path / "approved"
    value = redis_spec(tmp_path)
    create_resource_directories(RUN_ID, "redis", root)
    postgres = create_resource_directories(RUN_ID, "postgres", root)
    observation = normalize_docker_observation(
        parse_restricted_docker_observation(inspected(value), value), value)
    sentinel = value.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation), approved_root=root)
    fake = Fake(value); fake.ss_count = 1
    result = teardown_resource(
        sentinel_path=sentinel, run_id=RUN_ID, resource_type="redis",
        image=value.image, executor=fake, approved_root=root)
    assert result["state"] == "COMPLETE"
    assert result["resource_path_absent"] is True
    assert result["run_directory_absent"] is False
    assert result["run_directory_retained_for_sibling"] is True
    assert postgres.is_dir() and postgres.parent.is_dir() and root.is_dir()


def test_empty_run_directory_exact_rmdir_regression(tmp_path):
    root = tmp_path / "approved"
    resource = create_resource_directories(RUN_ID, "redis", root)
    run_directory = resource.parent
    resource.rmdir()
    assert run_directory.is_dir()
    assert remove_empty_run_directory(
        run_id=RUN_ID, resource_type="redis", approved_root=root) is True
    assert root.is_dir() and not run_directory.exists()


def test_expected_same_run_sibling_is_retained_without_failure(tmp_path):
    root = tmp_path / "approved"
    redis = create_resource_directories(RUN_ID, "redis", root)
    postgres = create_resource_directories(RUN_ID, "postgres", root)
    (postgres / "data").rmdir()
    redis.rmdir()
    assert remove_empty_run_directory(
        run_id=RUN_ID, resource_type="redis", approved_root=root) is False
    assert postgres.is_dir() and postgres.parent.is_dir()


def test_unexpected_run_content_fails_closed_and_is_preserved(tmp_path):
    root = tmp_path / "approved"
    resource = create_resource_directories(RUN_ID, "redis", root)
    run_directory = resource.parent
    resource.rmdir()
    unexpected = run_directory / "forensic-evidence"
    unexpected.write_text("preserve")
    with pytest.raises(OrchestrationError) as error:
        remove_empty_run_directory(
            run_id=RUN_ID, resource_type="redis", approved_root=root)
    assert error.value.category is FailureClass.TEARDOWN_EXECUTION_FAILED
    assert unexpected.read_text() == "preserve" and run_directory.is_dir()


@pytest.mark.parametrize("drift", ["mode", "uid", "gid"])
def test_run_directory_metadata_drift_is_rejected(tmp_path, monkeypatch, drift):
    root = tmp_path / "approved"
    resource = create_resource_directories(RUN_ID, "redis", root)
    run_directory = resource.parent
    if drift == "mode":
        run_directory.chmod(0o755)
    else:
        uid, gid = attestation.lifecycle_operator_identity()
        monkeypatch.setattr(
            "_integration_resource_lifecycle.lifecycle_operator_identity",
            lambda: (uid + (drift == "uid"), gid + (drift == "gid")),
        )
    with pytest.raises(attestation.ResourceAttestationError):
        validate_run_cleanup_path(run_directory, run_id=RUN_ID, approved_root=root)
    assert run_directory.exists()


def test_run_directory_symlink_and_wrong_parent_are_rejected(tmp_path):
    root = tmp_path / "approved"
    resource = create_resource_directories(RUN_ID, "redis", root)
    run_directory = resource.parent
    outside = tmp_path / "outside"; outside.mkdir(mode=0o700)
    link = root / "r22-fedcba9876543210"; link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(attestation.ResourceAttestationError):
        validate_run_cleanup_path(link, run_id="r22-fedcba9876543210", approved_root=root)
    with pytest.raises(attestation.ResourceAttestationError):
        validate_run_cleanup_path(outside, run_id=RUN_ID, approved_root=root)
    with pytest.raises(attestation.ResourceAttestationError):
        validate_run_cleanup_path(root, run_id=RUN_ID, approved_root=root)
    assert run_directory.exists() and outside.exists()


def test_teardown_open_port_fails_after_exact_container_removal(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value, port_closes=False); fake.ss_count = 1
    with pytest.raises(OrchestrationError):
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE,
                          executor=fake, approved_root=tmp_path / "approved")
    assert value.temp_dir.exists()


def test_teardown_identity_mismatch_never_stops_or_removes(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value); fake.ss_count = 1
    original = fake.run
    def mismatch(argv, **kwargs):
        if docker_subcommand(tuple(argv)) == "inspect" and not fake.removed:
            fake.calls.append((tuple(argv), kwargs))
            return CommandResult(0, inspected(value, labels={}))
        return original(argv, **kwargs)
    fake.run = mismatch
    with pytest.raises((OrchestrationError, Exception)):
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE,
                          executor=fake, approved_root=tmp_path / "approved")
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)


def test_execute_scripts_never_use_fixture_observation_branch():
    root = Path(__file__).resolve().parents[2]
    for name in ("run_integration_migration_cleanroom.py",
                 "teardown_integration_resources_cleanroom.py"):
        source = (root / "scripts" / name).read_text()
        execute = source.split("if args.execute:", 1)[1].split("return 0", 1)[0]
        assert "args.observation" not in execute


class FakeClock:
    def __init__(self): self.now = 0.0
    def monotonic(self): return self.now
    def sleep(self, duration): self.now += duration


def provision_fast(*args, **kwargs):
    clock = FakeClock()
    kwargs.update(stability_window=1.0, stability_interval=0.5,
                  monotonic=clock.monotonic, sleeper=clock.sleep)
    return provision_resource(*args, **kwargs)


def test_normal_teardown_rejects_exited_container(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value, start_fails=True)
    fake.ss_count = 1
    with pytest.raises(Exception):
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE, executor=fake,
                          approved_root=tmp_path / "approved")
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)


def test_normal_teardown_rejects_missing_listener(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value)
    with pytest.raises(OrchestrationError) as error:
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE, executor=fake,
                          approved_root=tmp_path / "approved")
    assert error.value.category is FailureClass.LISTENER_ATTESTATION_FAILED
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)


def test_metadata_owner_attestation_failure_preserves_post_create_resource(tmp_path, monkeypatch):
    value = spec(tmp_path); fake = Fake(value)
    real_write = flows.write_secure_json
    expected = attestation.lifecycle_operator_identity()
    drifted = {"value": False}

    def identity():
        return (expected[0] + 1, expected[1]) if drifted["value"] else expected

    def write_then_drift(path, payload, **kwargs):
        real_write(path, payload, **kwargs)
        if path.name == "sentinel.json":
            drifted["value"] = True

    monkeypatch.setattr(attestation, "lifecycle_operator_identity", identity)
    monkeypatch.setattr(flows, "write_secure_json", write_then_drift)
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake, approved_root=tmp_path / "approved")
    assert_review_required(error, FailureClass.SENTINEL_WRITE_FAILED)
    assert not any(docker_subcommand(argv) in {"stop", "rm"} for argv, _ in fake.calls)
    assert (value.temp_dir / "sentinel.json").is_file()
    assert (value.temp_dir / "observation.json").is_file()


def test_teardown_owner_drift_is_denied_without_docker_mutation(tmp_path, monkeypatch):
    value, sentinel = evidence(tmp_path); fake = Fake(value); fake.ss_count = 1
    uid, gid = attestation.lifecycle_operator_identity()
    monkeypatch.setattr(attestation, "lifecycle_operator_identity", lambda: (uid, gid + 1))
    with pytest.raises(attestation.ResourceAttestationError, match="GID"):
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE,
                          executor=fake, approved_root=tmp_path / "approved")
    assert fake.calls == []
    assert sentinel.is_file() and value.temp_dir.is_dir()
