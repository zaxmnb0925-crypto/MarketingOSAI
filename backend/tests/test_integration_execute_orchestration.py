"""Fake-only B5F tests. No real command may execute from this module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from _integration_execute_flows import (
    assert_same_run_resources, build_migration_execution, provision_resource,
    remove_exact_temp_path,
)
from _integration_execute_orchestration import (
    CommandResult, FailureClass, InventoryItem, ListenerObservation,
    OrchestrationError, collect_inventory, observe_listener,
    parse_restricted_docker_observation, provisional_rollback,
    reject_inventory_collision, require_loopback_listener, require_port_free,
    validate_provisional_observation,
)
from _integration_resource_attestation import ResourceAttestationError
from _integration_resource_lifecycle import (
    build_docker_spec, create_resource_directories, normalize_docker_observation,
    sentinel_payload, validate_image_reference, write_secure_json,
)

RUN_ID = "r22-0123456789abcdef"
PG_IMAGE = "docker.io/library/postgres@sha256:" + "a" * 64
REDIS_IMAGE = "docker.io/library/redis@sha256:" + "b" * 64
CID = "c" * 64


class FakeExecutor:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def run(self, argv, **kwargs):
        self.calls.append((tuple(argv), kwargs))
        return self.handler(tuple(argv), kwargs, len(self.calls))


def pg_spec(tmp_path: Path):
    return build_docker_spec(run_id=RUN_ID, resource_type="postgres", image=PG_IMAGE,
                             port=15432, approved_root=tmp_path / "approved")


def inspect_output(spec, *, cid=CID, digest=None, labels=None, host="127.0.0.1",
                   port=None, running=True, name=None, mounts=None):
    reference = spec.image if digest is None else spec.image.split("@", 1)[0] + "@" + digest
    values = [cid, "/" + (name or spec.container_name), reference,
              dict(spec.labels) if labels is None else labels, running,
              "2026-08-16T00:00:00Z", "bridge",
              {f"{spec.internal_port}/tcp": [{"HostIp": host,
                                               "HostPort": str(port or spec.port)}]},
              ([{"Source": str(spec.temp_dir), "Destination": "/var/lib/postgresql/data"}]
               if mounts is None and spec.resource_type == "postgres" else (mounts or []))]
    return "\n".join(json.dumps(value) for value in values)


def fake_success(tmp_path: Path, *, post_host="127.0.0.1"):
    spec = pg_spec(tmp_path)
    listener_count = 0

    def handler(argv, kwargs, _count):
        nonlocal listener_count
        if argv[1:3] == ("ps", "-a"):
            return CommandResult(0, "")
        if argv[0].endswith("/ss"):
            listener_count += 1
            return CommandResult(0, "" if listener_count == 1 else
                                 f"LISTEN 0 4096 {post_host}:{spec.port} 0.0.0.0:*\n")
        if argv[0].endswith("/lsof"):
            return CommandResult(1 if listener_count == 1 else 0,
                                 "" if listener_count == 1 else f"docker-proxy TCP {post_host}:{spec.port} (LISTEN)\n")
        if argv == spec.argv:
            return CommandResult(0, CID + "\n")
        if len(argv) > 1 and argv[1] == "start":
            return CommandResult(0, CID + "\n")
        if len(argv) > 1 and argv[1] == "inspect":
            return CommandResult(0, inspect_output(spec))
        if len(argv) > 1 and argv[1] in {"stop", "rm"}:
            return CommandResult(0, CID + "\n")
        raise AssertionError(f"unexpected fake command: {argv}")

    return spec, FakeExecutor(handler)


def prepared_evidence(tmp_path: Path):
    spec = pg_spec(tmp_path)
    create_resource_directories(RUN_ID, "postgres", tmp_path / "approved")
    raw = parse_restricted_docker_observation(inspect_output(spec), spec)
    observation = normalize_docker_observation(raw, spec)
    sentinel = spec.temp_dir / "sentinel.json"
    write_secure_json(sentinel, sentinel_payload(observation), approved_root=tmp_path / "approved")
    return spec, sentinel


def test_restricted_parser_returns_only_allowlisted_fields(tmp_path):
    spec = pg_spec(tmp_path)
    parsed = parse_restricted_docker_observation(inspect_output(spec), spec)
    assert set(parsed) == {"container_id", "container_name", "image_digest", "labels",
                           "running", "started_at", "networks", "published_host",
                           "published_port", "internal_port", "mount_sources"}
    assert "Env" not in parsed


def test_raw_environment_cannot_be_added_to_restricted_output(tmp_path):
    with pytest.raises(OrchestrationError):
        parse_restricted_docker_observation(inspect_output(pg_spec(tmp_path)) +
                                            '\n{"Env":["PASSWORD=redacted"]}', pg_spec(tmp_path))


def test_inventory_parser_keeps_only_identity_fields():
    raw = json.dumps({"ID": CID, "Names": "safe", "Labels": "a=b", "Networks": "bridge",
                      "Status": "ignored", "Ports": "ignored"})
    items = collect_inventory(FakeExecutor(lambda *_: CommandResult(0, raw)))
    assert items == (InventoryItem(CID, "safe", {"a": "b"}, ("bridge",), ""),)


@pytest.mark.parametrize("collision", [
    "name", "run-label", "different-type", "different-name", "different-image",
])
def test_inventory_collisions_reject(tmp_path, collision):
    spec = pg_spec(tmp_path)
    name, labels, image = "other", {}, "unrelated@sha256:" + "d" * 64
    if collision == "name": name = spec.container_name
    if collision == "run-label": labels = {"com.marketingos.test-run-id": RUN_ID}
    if collision == "different-type": labels = {
        "com.marketingos.test-run-id": RUN_ID,
        "com.marketingos.test-resource-type": "redis",
    }
    if collision in {"different-name", "different-image"}:
        labels = {"com.marketingos.test-run-id": RUN_ID}
    with pytest.raises(OrchestrationError) as error:
        reject_inventory_collision((InventoryItem(CID, name, labels, ("bridge",), image),), spec)
    assert error.value.category is FailureClass.INVENTORY_COLLISION


@pytest.mark.parametrize("labels", [{}, {"foreign.example/owner": "other"}])
def test_unrelated_inventory_is_allowed(tmp_path, labels):
    reject_inventory_collision(
        (InventoryItem(CID, "unrelated", labels, ("bridge",), "unrelated:1"),),
        pg_spec(tmp_path),
    )


def test_malformed_inventory_ownership_is_rejected(tmp_path):
    malformed = InventoryItem(CID, "unrelated", None, ("bridge",))  # type: ignore[arg-type]
    with pytest.raises(OrchestrationError) as error:
        reject_inventory_collision((malformed,), pg_spec(tmp_path))
    assert error.value.category is FailureClass.INVENTORY_COLLISION


def test_pre_port_collision_rejects():
    with pytest.raises(OrchestrationError) as error:
        require_port_free(ListenerObservation("127.0.0.1", 15432, "LISTEN", ""))
    assert error.value.category is FailureClass.PORT_COLLISION


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "", "192.0.2.10"])
def test_non_loopback_listener_rejects(host):
    with pytest.raises(OrchestrationError):
        require_loopback_listener(ListenerObservation(host, 15432, "LISTEN", ""))


def test_listener_observer_uses_only_fake_commands():
    fake = FakeExecutor(lambda argv, _kwargs, _n: CommandResult(0, "") if argv[0].endswith("/ss") else CommandResult(1, ""))
    assert observe_listener(fake, 15432).host == ""
    assert len(fake.calls) == 2


@pytest.mark.parametrize("field,value", [
    ("container_id", "d" * 64), ("container_name", "wrong"),
    ("image_digest", "sha256:" + "d" * 64), ("labels", {}),
    ("published_host", "0.0.0.0"), ("published_port", 15433),
    ("networks", ["production"]), ("mount_sources", ["/opt/MarketingOSAI"]),
])
def test_provisional_identity_mismatch_rejects(tmp_path, field, value):
    spec = pg_spec(tmp_path)
    raw = parse_restricted_docker_observation(inspect_output(spec), spec)
    raw[field] = value
    with pytest.raises(OrchestrationError):
        validate_provisional_observation(raw, spec, CID)


def test_successful_provision_orders_attestation_before_sentinel(tmp_path):
    spec, fake = fake_success(tmp_path)
    result = provision_resource(spec, executor=fake, runtime_password="runtime-only",
                                approved_root=tmp_path / "approved")
    assert result["states"] == ("PRECHECK", "TEMP_ROOT_CREATED", "PRE_PORT_FREE",
        "CONTAINER_CREATED", "EXACT_CONTAINER_ID_CAPTURED", "CONTAINER_STARTED",
        "DOCKER_OBSERVED", "LISTENER_OBSERVED", "ATTESTED", "SENTINEL_WRITTEN", "READY")
    assert Path(result["sentinel"]).stat().st_mode & 0o777 == 0o600


def test_runtime_password_only_reaches_create_child(tmp_path):
    spec, fake = fake_success(tmp_path)
    provision_resource(spec, executor=fake, runtime_password="runtime-only",
                       approved_root=tmp_path / "approved")
    secret_calls = [(argv, kwargs) for argv, kwargs in fake.calls if
                    kwargs.get("env", {}).get("POSTGRES_PASSWORD")]
    assert len(secret_calls) == 1 and secret_calls[0][0] == spec.argv
    assert all("runtime-only" not in " ".join(argv) for argv, _ in fake.calls)


def test_inherited_environment_is_not_propagated(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-inherit")
    spec, fake = fake_success(tmp_path)
    provision_resource(spec, executor=fake, runtime_password="runtime-only",
                       approved_root=tmp_path / "approved")
    assert all("AWS_SECRET_ACCESS_KEY" not in kwargs.get("env", {}) for _, kwargs in fake.calls)


def test_create_failure_is_sanitized(tmp_path):
    spec, fake = fake_success(tmp_path)
    original = fake.handler
    fake.handler = lambda argv, kwargs, n: (_ for _ in ()).throw(RuntimeError("password=leak")) if argv == spec.argv else original(argv, kwargs, n)
    with pytest.raises(OrchestrationError) as error:
        provision_resource(spec, executor=fake, runtime_password="runtime-only",
                           approved_root=tmp_path / "approved")
    assert str(error.value) == "CREATE_FAILED"


def test_provisional_rollback_uses_exact_id(tmp_path):
    spec = pg_spec(tmp_path)
    fake = FakeExecutor(lambda argv, _kwargs, _n: CommandResult(0, inspect_output(spec))
                        if argv[1] == "inspect" else CommandResult(0, ""))
    assert provisional_rollback(fake, spec, CID)
    assert all(call[0][-1] == CID for call in fake.calls)


def test_rollback_mismatch_preserves_resource(tmp_path):
    spec = pg_spec(tmp_path)
    fake = FakeExecutor(lambda *_: CommandResult(0, inspect_output(spec, labels={})))
    with pytest.raises(OrchestrationError) as error:
        provisional_rollback(fake, spec, CID)
    assert error.value.category is FailureClass.ROLLBACK_AUTHORIZATION_FAILED
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in fake.calls)


def test_atomic_write_rejects_existing_and_leaves_no_temp(tmp_path):
    spec = pg_spec(tmp_path); create_resource_directories(RUN_ID, "postgres", tmp_path / "approved")
    payload = {"resource_run_id": RUN_ID, "resource_type": "postgres", "value": "safe"}
    target = spec.temp_dir / "evidence.json"
    write_secure_json(target, payload, approved_root=tmp_path / "approved")
    with pytest.raises(ResourceAttestationError):
        write_secure_json(target, payload, approved_root=tmp_path / "approved")
    assert not list(spec.temp_dir.glob(".*.tmp"))


def test_migration_builds_exact_argv_cwd_and_scrubbed_env(tmp_path):
    spec, sentinel = prepared_evidence(tmp_path)
    fake = FakeExecutor(lambda argv, _kwargs, _n: CommandResult(0, inspect_output(spec))
                        if argv[0].endswith("docker") else
                        CommandResult(0, f"LISTEN 0 1 127.0.0.1:{spec.port} 0.0.0.0:*\n")
                        if argv[0].endswith("ss") else CommandResult(0, f"x :{spec.port}"))
    argv, env, cwd = build_migration_execution(
        sentinel_path=sentinel, run_id=RUN_ID, image=PG_IMAGE,
        runtime_password="runtime-only", executor=fake, approved_root=tmp_path / "approved")
    assert argv[-2:] == ("upgrade", "7c91e2f4b6a8") and cwd.name == "backend"
    assert env["DATABASE_URL"].startswith("postgresql+asyncpg://")
    assert "POSTGRES_TEST_PASSWORD" not in env and set(env) <= {"PATH", "LANG", "DATABASE_URL",
        "ENVIRONMENT", "MARKETINGOS_TEST_MODE", "MARKETINGOS_TEST_RESOURCE_SCOPE", "TEST_RUN_ID"}


def test_migration_wrong_run_rejects_before_commands(tmp_path):
    _, sentinel = prepared_evidence(tmp_path); fake = FakeExecutor(lambda *_: pytest.fail("command called"))
    with pytest.raises(ResourceAttestationError):
        build_migration_execution(sentinel_path=sentinel, run_id="r22-fedcba9876543210",
                                  image=PG_IMAGE, runtime_password="x", executor=fake,
                                  approved_root=tmp_path / "approved")


def test_migration_missing_password_rejects(tmp_path):
    spec, sentinel = prepared_evidence(tmp_path)
    fake = FakeExecutor(lambda argv, _kwargs, _n: CommandResult(0, inspect_output(spec))
                        if argv[0].endswith("docker") else
                        CommandResult(0, f"LISTEN 0 1 127.0.0.1:{spec.port} 0.0.0.0:*"))
    with pytest.raises(ResourceAttestationError):
        build_migration_execution(sentinel_path=sentinel, run_id=RUN_ID, image=PG_IMAGE,
                                  runtime_password="", executor=fake,
                                  approved_root=tmp_path / "approved")


@pytest.mark.parametrize("redis_run,required,passes", [
    (RUN_ID, True, True), ("r22-fedcba9876543210", True, False),
    (None, True, False), (None, False, True), (RUN_ID, False, False),
])
def test_same_run_resource_enforcement(redis_run, required, passes):
    if passes:
        assert_same_run_resources(RUN_ID, redis_run, redis_required=required)
    else:
        with pytest.raises(OrchestrationError):
            assert_same_run_resources(RUN_ID, redis_run, redis_required=required)


@pytest.mark.parametrize("unsafe", [Path("/"), Path("/tmp"), Path("/home"), Path("/opt")])
def test_unsafe_temp_cleanup_rejected(tmp_path, unsafe):
    with pytest.raises((ResourceAttestationError, OSError)):
        remove_exact_temp_path(unsafe, run_id=RUN_ID, resource_type="postgres",
                               approved_root=tmp_path / "approved")


def test_source_has_no_unsafe_command_forms_or_fixture_execute_bypass():
    root = Path(__file__).resolve().parents[2]
    sources = "\n".join(path.read_text() for path in [
        root / "backend/tests/_integration_execute_orchestration.py",
        root / "backend/tests/_integration_execute_flows.py",
        root / "scripts/run_integration_migration_cleanroom.py",
        root / "scripts/teardown_integration_resources_cleanroom.py",
    ])
    assert "shell=True" not in sources
    assert "os.system" not in sources and "eval(" not in sources
    for script in ("run_integration_migration_cleanroom.py", "teardown_integration_resources_cleanroom.py"):
        text = (root / "scripts" / script).read_text()
        execute = text.split("if args.execute:", 1)[1].split("return 0", 1)[0]
        assert "args.observation" not in execute


def test_no_real_subprocess_can_run_in_b5f_tests(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("real command attempted"))
    spec = build_docker_spec(run_id=RUN_ID, resource_type="redis", image=REDIS_IMAGE,
                             port=16379, approved_root=Path("/tmp/unused-b5f-test"))
    parsed = parse_restricted_docker_observation(inspect_output(spec, mounts=[]), spec)
    assert parsed["container_id"] == CID



def test_documented_b5e_candidates_are_immutable_references():
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    postgres = "docker.io/library/postgres@sha256:075f7ba66bc9b3ce7d6b8b635208ff61cd7cf1a67d71ec530eec5d7ae0cbe571"
    redis = "docker.io/library/redis@sha256:9702d01c1f10c3ea9f48211b4362e44f154ff02d063e6f7268eba804059f53bf"
    assert readme.count(postgres) == 1 and readme.count(redis) == 1
    assert validate_image_reference(postgres).startswith("sha256:")
    assert validate_image_reference(redis).startswith("sha256:")
    for invalid in ("postgres:" + "a" * 64, "postgres:16-alpine", "postgres:latest",
                    "postgres@sha256:abc"):
        with pytest.raises(ResourceAttestationError):
            validate_image_reference(invalid)
