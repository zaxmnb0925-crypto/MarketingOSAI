"""Additional fake-only rollback and teardown safety cases for B5F."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import _integration_execute_flows as flows
from _integration_execute_flows import provision_resource, teardown_resource
from _integration_execute_orchestration import CommandResult, FailureClass, OrchestrationError
from _integration_resource_lifecycle import (
    build_docker_spec, create_resource_directories, normalize_docker_observation,
    sentinel_payload, write_secure_json,
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


def inspected(value, *, running=True, labels=None):
    values = [CID, "/" + value.container_name, value.image,
              dict(value.labels) if labels is None else labels, running,
              "2026-08-16T00:00:00Z", "bridge",
              {f"{value.internal_port}/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(value.port)}]},
              ([{"Type": "bind", "Source": str(value.pgdata_dir),
                 "Destination": "/var/lib/postgresql/data", "RW": True}]
               if value.resource_type == "postgres" else
               [{"Type": "tmpfs", "Source": "", "Destination": "/data", "RW": True}])]
    return "\n".join(json.dumps(item) for item in values)


class Fake:
    def __init__(self, value, *, start_fails=False, port_closes=True):
        self.value, self.start_fails, self.port_closes = value, start_fails, port_closes
        self.calls, self.ss_count, self.removed = [], 0, False

    def run(self, argv, **kwargs):
        argv = tuple(argv); self.calls.append((argv, kwargs))
        if argv[1:3] == ("ps", "-a"): return CommandResult(0, "")
        if argv[0].endswith("/ss"):
            self.ss_count += 1
            open_now = self.ss_count > 1 and not (self.removed and self.port_closes)
            return CommandResult(0, f"LISTEN 0 1 127.0.0.1:{self.value.port} 0.0.0.0:*\n" if open_now else "")
        if argv[0].endswith("/lsof"):
            open_now = self.ss_count > 1 and not (self.removed and self.port_closes)
            return CommandResult(0 if open_now else 1,
                                 f"docker-proxy TCP 127.0.0.1:{self.value.port} (LISTEN)" if open_now else "")
        if argv == self.value.argv: return CommandResult(0, CID + "\n")
        if argv[1] == "start":
            if self.start_fails: raise RuntimeError("synthetic start failure")
            return CommandResult(0, CID + "\n")
        if argv[1] == "inspect":
            if self.removed: return CommandResult(1, "")
            return CommandResult(0, inspected(self.value, running=not self.start_fails))
        if argv[1] == "stop": return CommandResult(0, CID + "\n")
        if argv[1] == "rm": self.removed = True; return CommandResult(0, CID + "\n")
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
    assert [argv[1:] for argv, _ in fake.calls if argv[1] in {"stop", "rm"}] == [
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
        if tuple(argv)[1] == "inspect" and not fake.removed:
            fake.calls.append((tuple(argv), kwargs))
            mounts = [{"Type": "volume", "Source": "anonymous-id",
                       "Destination": "/data", "RW": True}]
            return CommandResult(0, inspected(value).rsplit("\n", 1)[0] +
                                 "\n" + json.dumps(mounts))
        return original(argv, **kwargs)
    fake.run = volume_instead_of_tmpfs
    with pytest.raises(Exception):
        teardown_resource(
            sentinel_path=sentinel, run_id=RUN_ID, resource_type="redis",
            image=value.image, executor=fake, approved_root=tmp_path / "approved")
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in fake.calls)


def test_start_failure_runs_provisional_exact_id_rollback(tmp_path):
    value = spec(tmp_path); fake = Fake(value, start_fails=True)
    with pytest.raises(OrchestrationError) as error:
        provision_fast(value, executor=fake,
                           approved_root=tmp_path / "approved")
    assert error.value.category is FailureClass.START_FAILED
    assert any(argv[1:] == ("rm", CID) for argv, _ in fake.calls)
    assert not any(argv[1:] == ("stop", CID) for argv, _ in fake.calls)


def test_sentinel_write_failure_triggers_exact_rollback(tmp_path, monkeypatch):
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
    assert error.value.category is FailureClass.SENTINEL_WRITE_FAILED
    assert any(argv[1:] == ("rm", CID) for argv, _ in fake.calls)


def test_teardown_uses_fresh_observation_exact_id_and_closes_port(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value); fake.ss_count = 1
    result = teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                               resource_type="postgres", image=IMAGE,
                               executor=fake, approved_root=tmp_path / "approved")
    assert result == {"state": "COMPLETE", "container_id": CID, "path_absent": True}
    assert [argv[1:] for argv, _ in fake.calls if argv[1] in {"stop", "rm"}] == [("stop", CID), ("rm", CID)]
    assert fake.ss_count == 3


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
        if tuple(argv)[1] == "inspect" and not fake.removed:
            fake.calls.append((tuple(argv), kwargs))
            return CommandResult(0, inspected(value, labels={}))
        return original(argv, **kwargs)
    fake.run = mismatch
    with pytest.raises((OrchestrationError, Exception)):
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE,
                          executor=fake, approved_root=tmp_path / "approved")
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in fake.calls)


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
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in fake.calls)


def test_normal_teardown_rejects_missing_listener(tmp_path):
    value, sentinel = evidence(tmp_path); fake = Fake(value)
    with pytest.raises(OrchestrationError) as error:
        teardown_resource(sentinel_path=sentinel, run_id=RUN_ID,
                          resource_type="postgres", image=IMAGE, executor=fake,
                          approved_root=tmp_path / "approved")
    assert error.value.category is FailureClass.LISTENER_ATTESTATION_FAILED
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in fake.calls)
