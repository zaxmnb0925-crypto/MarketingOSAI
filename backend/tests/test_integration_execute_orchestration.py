"""Fake-only B5F tests. No real command may execute from this module."""
from __future__ import annotations

import json
from pathlib import Path
import runpy
import sys

import pytest

import _integration_execute_flows as flows
import _integration_resource_lifecycle as lifecycle
from _integration_docker_command import DOCKER_PRIVILEGE_PREFIX, docker_subcommand
from _integration_execute_flows import (
    assert_same_run_resources, build_migration_execution, provision_resource,
    remove_exact_temp_path,
)
from _integration_execute_orchestration import (
    CommandResult, FailureClass, InventoryItem, ListenerObservation,
    OrchestrationError, collect_inventory, observe_lifecycle_stability, observe_listener,
    parse_restricted_docker_observation,
    reject_inventory_collision, require_loopback_listener, require_port_free,
    validate_provisional_observation,
)
from _integration_resource_attestation import ResourceAttestationError
from _integration_resource_lifecycle import (
    build_docker_spec, create_resource_directories, normalize_docker_observation,
    postgres_password_file_path, read_postgres_password_file, sentinel_payload,
    validate_image_reference, write_secure_json,
)

RUN_ID = "r22-0123456789abcdef"
PG_IMAGE = "docker.io/library/postgres@sha256:" + "a" * 64
REDIS_IMAGE = "docker.io/library/redis@sha256:" + "b" * 64
CID = "c" * 64
SYNTHETIC_SECRET = "S" * 43


class FakeExecutor:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def run(self, argv, **kwargs):
        recorded = dict(kwargs)
        if "env" in recorded:
            recorded["env"] = dict(recorded["env"])
        self.calls.append((tuple(argv), recorded))
        return self.handler(tuple(argv), kwargs, len(self.calls))


def pg_spec(tmp_path: Path):
    return build_docker_spec(run_id=RUN_ID, resource_type="postgres", image=PG_IMAGE,
                             port=15432, approved_root=tmp_path / "approved")


def redis_spec(tmp_path: Path):
    return build_docker_spec(run_id=RUN_ID, resource_type="redis", image=REDIS_IMAGE,
                             port=16379, approved_root=tmp_path / "approved")


def inspect_output(spec, *, cid=CID, digest=None, labels=None, host="127.0.0.1",
                   port=None, running=True, name=None, mounts=None,
                   started="2026-08-16T00:00:00Z", host_tmpfs=None,
                   declared_volumes=None):
    reference = spec.image if digest is None else spec.image.split("@", 1)[0] + "@" + digest
    values = [cid, "/" + (name or spec.container_name), reference,
              dict(spec.labels) if labels is None else labels, running,
              started, "bridge",
              {f"{spec.internal_port}/tcp": [{"HostIp": host,
                                               "HostPort": str(port or spec.port)}]},
              ([{"Type": "bind", "Source": str(spec.pgdata_dir),
                 "Destination": "/var/lib/postgresql/data", "RW": True}]
               if mounts is None and spec.resource_type == "postgres" else
               ([] if mounts is None else mounts)),
              (host_tmpfs if host_tmpfs is not None else
               ({} if spec.resource_type == "postgres" else
                {"/data": "rw,size=67108864,mode=0700"})),
              (declared_volumes if declared_volumes is not None else
               ({"/var/lib/postgresql/data": {}} if spec.resource_type == "postgres"
                else {"/data": {}}))]
    return "\n".join(json.dumps(value) for value in values)


def fake_success(tmp_path: Path, *, post_host="127.0.0.1"):
    spec = pg_spec(tmp_path)
    listener_count = 0

    def handler(argv, kwargs, _count):
        nonlocal listener_count
        if docker_subcommand(argv) == "ps":
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
        if docker_subcommand(argv) == "start":
            return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "inspect":
            return CommandResult(0, inspect_output(spec))
        if len(argv) > 1 and docker_subcommand(argv) in {"stop", "rm"}:
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
                           "published_port", "internal_port", "mount_sources",
                           "mount_details", "host_tmpfs",
                           "declared_volumes"}
    assert "Env" not in parsed


def test_raw_environment_cannot_be_added_to_restricted_output(tmp_path):
    with pytest.raises(OrchestrationError):
        parse_restricted_docker_observation(inspect_output(pg_spec(tmp_path)) +
                                            '\n{"Env":["PASSWORD=redacted"]}', pg_spec(tmp_path))


def inventory_row(*, cid=CID, name="safe", test_resource="", run_id="",
                  resource_type=""):
    return "\t".join((cid, name, test_resource, run_id, resource_type))


def test_inventory_command_and_parser_are_fixed_field_minimal():
    fake = FakeExecutor(lambda *_: CommandResult(0, inventory_row()))
    items = collect_inventory(fake)
    assert items == (InventoryItem(CID, "safe", "", "", ""),)
    argv = fake.calls[0][0]
    assert argv[:8] == (*DOCKER_PRIVILEGE_PREFIX, "ps", "-a", "--no-trunc", "--format", argv[7])
    assert argv[7] == "\t".join((
        "{{.ID}}", "{{.Names}}",
        '{{.Label "com.marketingos.test-resource"}}',
        '{{.Label "com.marketingos.test-run-id"}}',
        '{{.Label "com.marketingos.test-resource-type"}}',
    ))
    assert "{{json .}}" not in argv[5]
    for prohibited in (".Command", ".Labels", ".Mounts", ".Image", ".Ports", ".Created", ".Size", ".Env"):
        assert prohibited not in argv[5]


def test_unrelated_unlabeled_inventory_parses_safely():
    items = collect_inventory(FakeExecutor(lambda *_: CommandResult(0, inventory_row())))
    reject_inventory_collision(items, pg_spec(Path("/tmp/b5j-unrelated")))


@pytest.mark.parametrize("collision", [
    "name", "run-label", "different-type", "different-name", "stopped-same-run",
])
def test_inventory_collisions_reject(tmp_path, collision):
    spec = pg_spec(tmp_path)
    name, run_id, resource_type = "other", "r22-fedcba9876543210", "redis"
    if collision == "name":
        name = spec.container_name
    else:
        run_id = RUN_ID
    if collision == "different-type":
        resource_type = "redis"
    item = InventoryItem(CID, name, "true", run_id, resource_type)
    with pytest.raises(OrchestrationError) as error:
        reject_inventory_collision((item,), spec)
    assert error.value.category is FailureClass.INVENTORY_COLLISION


def test_unrelated_inventory_is_allowed(tmp_path):
    reject_inventory_collision(
        (InventoryItem(CID, "unrelated", "", "r22-fedcba9876543210", ""),),
        pg_spec(tmp_path),
    )


def test_malformed_inventory_ownership_is_rejected(tmp_path):
    malformed = InventoryItem(CID, "unrelated", "", None, "")  # type: ignore[arg-type]
    with pytest.raises(OrchestrationError) as error:
        reject_inventory_collision((malformed,), pg_spec(tmp_path))
    assert error.value.category is FailureClass.INVENTORY_COLLISION


@pytest.mark.parametrize("raw", [
    "malformed",
    "\t".join((CID, "safe", "", "")),
    "\t".join((CID, "safe", "", "", "", "unexpected")),
    "\t".join(("not-an-id", "safe", "", "", "")),
    "\t".join((CID, "bad name", "", "", "")),
])
def test_malformed_inventory_fails_closed_without_echo(raw):
    with pytest.raises(OrchestrationError) as error:
        collect_inventory(FakeExecutor(lambda *_: CommandResult(0, raw)))
    assert error.value.category is FailureClass.DOCKER_OBSERVATION_FAILED
    assert raw not in str(error.value)


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


def test_redis_tmpfs_provision_preserves_stability_and_post_sentinel_ready(tmp_path):
    spec = redis_spec(tmp_path)
    listener_count = 0
    inspect_count = 0
    def handler(argv, kwargs, _count):
        nonlocal listener_count, inspect_count
        if docker_subcommand(argv) == "ps": return CommandResult(0, "")
        if argv[0].endswith("/ss"):
            listener_count += 1
            return CommandResult(0, "" if listener_count == 1 else
                                 f"LISTEN 0 4096 127.0.0.1:{spec.port} 0.0.0.0:*\n")
        if argv[0].endswith("/lsof"):
            return CommandResult(1 if listener_count == 1 else 0, "" if listener_count == 1 else
                                 f"docker-proxy TCP 127.0.0.1:{spec.port} (LISTEN)\n")
        if argv == spec.argv: return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "start": return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "inspect":
            inspect_count += 1
            return CommandResult(0, inspect_output(spec))
        raise AssertionError(argv)
    result = provision_fast(spec, executor=FakeExecutor(handler),
                            approved_root=tmp_path / "approved")
    assert result["state"] == "READY"
    assert "STABILITY_OBSERVED" in result["states"]
    assert result["states"][-2:] == ("POST_SENTINEL_OBSERVED", "READY")
    assert inspect_count >= 2


def test_redis_stability_rejects_hostconfig_tmpfs_drift(tmp_path):
    spec = redis_spec(tmp_path)
    baseline = parse_restricted_docker_observation(inspect_output(spec), spec)
    calls = 0
    def handler(argv, kwargs, _count):
        nonlocal calls
        if argv[0].endswith("/ss"):
            return CommandResult(0, f"LISTEN 0 1 127.0.0.1:{spec.port} 0.0.0.0:*\n")
        if argv[0].endswith("/lsof"):
            return CommandResult(0, f"docker-proxy TCP 127.0.0.1:{spec.port} (LISTEN)")
        if docker_subcommand(argv) == "inspect":
            calls += 1
            return CommandResult(0, inspect_output(
                spec, host_tmpfs={"/data": "rw,size=1024,mode=0700"}))
        raise AssertionError(argv)
    clock = FakeClock()
    with pytest.raises(OrchestrationError):
        observe_lifecycle_stability(
            FakeExecutor(handler), spec, CID, baseline, window=1.0, interval=0.5,
            monotonic=clock.monotonic, sleeper=clock.sleep)
    assert calls >= 1


def test_successful_provision_orders_attestation_before_sentinel(tmp_path):
    spec, fake = fake_success(tmp_path)
    result = provision_fast(
        spec, executor=fake, approved_root=tmp_path / "approved",
        secret_factory=lambda: SYNTHETIC_SECRET,
    )
    assert result["states"] == ("PRECHECK", "TEMP_ROOT_CREATED", "PGDATA_CREATED",
        "PGDATA_EMPTY_VERIFIED", "PRE_PORT_FREE", "CONTAINER_CREATED",
        "EXACT_CONTAINER_ID_CAPTURED", "CONTAINER_STARTED", "DOCKER_OBSERVED",
        "LISTENER_OBSERVED", "STABILITY_OBSERVED", "ATTESTED",
        "SENTINEL_WRITTEN", "POST_SENTINEL_OBSERVED", "READY")
    assert Path(result["sentinel"]).stat().st_mode & 0o777 == 0o600


def test_secret_generated_once_and_only_reaches_transient_env_file(
        tmp_path, capsys, monkeypatch):
    spec, fake = fake_success(tmp_path)
    calls = []
    transport_events = []

    real_write = flows.write_postgres_docker_env_file
    real_remove = flows.remove_postgres_docker_env_file

    def generate():
        calls.append(True)
        return SYNTHETIC_SECRET

    def tracked_write(path, password, **kwargs):
        assert password == SYNTHETIC_SECRET

        real_write(
            path,
            password,
            **kwargs,
        )

        transport_events.append(
            (
                "written",
                path,
                path.read_text(encoding="ascii"),
            )
        )

    def tracked_remove(path, **kwargs):
        transport_events.append(
            ("before_remove", path, path.exists())
        )

        real_remove(
            path,
            **kwargs,
        )

        transport_events.append(
            ("removed", path, path.exists())
        )

    monkeypatch.setattr(
        flows,
        "write_postgres_docker_env_file",
        tracked_write,
    )
    monkeypatch.setattr(
        flows,
        "remove_postgres_docker_env_file",
        tracked_remove,
    )

    result = provision_fast(
        spec,
        executor=fake,
        approved_root=tmp_path / "approved",
        secret_factory=generate,
    )

    assert len(calls) == 1

    transport = spec.temp_dir / "postgres-docker.env"

    assert transport_events == [
        (
            "written",
            transport,
            f"POSTGRES_PASSWORD={SYNTHETIC_SECRET}" + chr(10),
        ),
        ("before_remove", transport, True),
        ("removed", transport, False),
    ]

    create_calls = [
        (argv, kwargs)
        for argv, kwargs in fake.calls
        if argv == spec.argv
    ]

    assert len(create_calls) == 1

    argv, kwargs = create_calls[0]

    assert SYNTHETIC_SECRET not in " ".join(argv)
    assert set(kwargs["env"]) == {"PATH", "LANG"}
    assert "POSTGRES_PASSWORD" not in kwargs["env"]

    assert not transport.exists()

    assert SYNTHETIC_SECRET not in json.dumps(
        spec.sanitized_plan()
    )
    assert SYNTHETIC_SECRET not in json.dumps(result)
    assert SYNTHETIC_SECRET not in Path(
        result["sentinel"]
    ).read_text()
    assert SYNTHETIC_SECRET not in (
        spec.temp_dir / "observation.json"
    ).read_text()

    assert not [
        candidate
        for candidate in spec.temp_dir.iterdir()
        if candidate.is_file()
        and SYNTHETIC_SECRET in candidate.read_text()
    ]

    captured = capsys.readouterr()

    assert SYNTHETIC_SECRET not in captured.out
    assert SYNTHETIC_SECRET not in captured.err



def test_default_csprng_is_invoked_once_with_32_bytes(tmp_path, monkeypatch):
    spec, fake = fake_success(tmp_path); calls = []
    def generate(byte_count):
        calls.append(byte_count)
        return SYNTHETIC_SECRET
    monkeypatch.setattr(flows.secrets, "token_urlsafe", generate)
    provision_fast(spec, executor=fake, approved_root=tmp_path / "approved")
    assert calls == [32]


@pytest.mark.parametrize("name", ["POSTGRES_TEST_PASSWORD", "POSTGRES_PASSWORD"])
def test_inherited_postgres_secret_rejected_before_commands(tmp_path, monkeypatch, name):
    monkeypatch.setenv(name, "operator-value-must-not-appear")
    spec, fake = fake_success(tmp_path)
    with pytest.raises(OrchestrationError) as error:
        provision_fast(spec, executor=fake, approved_root=tmp_path / "approved")
    assert error.value.category is FailureClass.EXTERNAL_POSTGRES_SECRET_FORBIDDEN
    assert str(error.value) == "EXTERNAL_POSTGRES_SECRET_FORBIDDEN"
    assert fake.calls == []
    assert not spec.temp_dir.exists()


def test_inherited_unapproved_environment_is_not_propagated(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-inherit")
    spec, fake = fake_success(tmp_path)
    provision_fast(
        spec, executor=fake, approved_root=tmp_path / "approved",
        secret_factory=lambda: SYNTHETIC_SECRET,
    )
    assert all("AWS_SECRET_ACCESS_KEY" not in kwargs.get("env", {}) for _, kwargs in fake.calls)


def test_secret_generation_failure_is_sanitized_and_prevents_create(tmp_path):
    spec, fake = fake_success(tmp_path)
    def fail_generation():
        raise RuntimeError("sensitive-generator-detail")
    with pytest.raises(OrchestrationError) as error:
        provision_fast(
            spec, executor=fake, approved_root=tmp_path / "approved",
            secret_factory=fail_generation,
        )
    assert error.value.category is FailureClass.SECRET_GENERATION_FAILED
    assert str(error.value) == "SECRET_GENERATION_FAILED"
    assert not any(argv == spec.argv for argv, _ in fake.calls)
    assert list(spec.temp_dir.iterdir()) == [spec.pgdata_dir]


def test_short_or_non_text_generated_secret_fails_closed(tmp_path):
    for invalid in ("short", b"S" * 64):
        spec, fake = fake_success(tmp_path)
        with pytest.raises(OrchestrationError) as error:
            provision_fast(
                spec, executor=fake, approved_root=tmp_path / "approved",
                secret_factory=lambda invalid=invalid: invalid,
            )
        assert error.value.category is FailureClass.SECRET_GENERATION_FAILED
        assert not any(argv == spec.argv for argv, _ in fake.calls)
        if spec.temp_dir.exists():
            spec.pgdata_dir.rmdir()
            spec.temp_dir.rmdir()


def test_ambiguous_create_failure_preserves_for_review_without_cleanup(tmp_path):
    spec, fake = fake_success(tmp_path)
    original = fake.handler
    fake.handler = lambda argv, kwargs, n: (_ for _ in ()).throw(
        RuntimeError(SYNTHETIC_SECRET)) if argv == spec.argv else original(argv, kwargs, n)
    with pytest.raises(OrchestrationError) as error:
        provision_fast(
            spec, executor=fake, approved_root=tmp_path / "approved",
            secret_factory=lambda: SYNTHETIC_SECRET,
        )
    assert error.value.category is FailureClass.PROVISION_FAILED_REVIEW_REQUIRED
    assert error.value.original_category is FailureClass.CREATE_FAILED
    assert error.value.ownership_boundary == "CREATE_AMBIGUOUS_PRESERVE"
    assert error.value.resource_preserved is True
    assert str(error.value) == "PROVISION_FAILED_REVIEW_REQUIRED"
    assert SYNTHETIC_SECRET not in str(error.value)
    assert not any(docker_subcommand(argv) in {"stop", "rm", "kill"} for argv, _ in fake.calls)
    assert not any("--filter" in argv for argv, _ in fake.calls)
    assert spec.temp_dir.exists()


def test_dry_run_has_no_external_secret_requirement_or_generation(tmp_path, monkeypatch, capsys):
    script = Path(__file__).resolve().parents[2] / "scripts/provision_integration_resources_cleanroom.py"
    password_path = postgres_password_file_path(RUN_ID)
    monkeypatch.setattr(sys, "argv", [str(script), "postgres", "--image", PG_IMAGE,
                                     "--port", "15432", "--run-id", RUN_ID,
                                     "--postgres-password-file", str(password_path)])
    monkeypatch.setattr("_integration_execute_flows.secrets.token_urlsafe",
                        lambda *_: pytest.fail("secret generated during dry-run"))
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(script), run_name="__main__")
    assert result.value.code == 0
    output = capsys.readouterr().out
    assert '"mode": "DRY_RUN"' in output
    assert SYNTHETIC_SECRET not in output
    source = script.read_text()
    assert "--postgres-password <" not in source
    assert "postgres_password_file_handoff" in output


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
                        if docker_subcommand(argv) is not None else
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
                        if docker_subcommand(argv) is not None else
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

class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


def stability_fake(spec, inspect_values, *, listener_fails_after=None):
    values = list(inspect_values); listener_checks = 0
    def handler(argv, _kwargs, _count):
        nonlocal listener_checks
        if argv[0].endswith("/ss"):
            listener_checks += 1
            open_now = listener_fails_after is None or listener_checks <= listener_fails_after
            return CommandResult(0, f"LISTEN 0 1 127.0.0.1:{spec.port} 0.0.0.0:*\n" if open_now else "")
        if argv[0].endswith("/lsof"):
            open_now = listener_fails_after is None or listener_checks <= listener_fails_after
            return CommandResult(0 if open_now else 1,
                                 f"docker-proxy TCP 127.0.0.1:{spec.port} (LISTEN)" if open_now else "")
        if docker_subcommand(argv) == "inspect":
            return CommandResult(0, values.pop(0))
        raise AssertionError(argv)
    return FakeExecutor(handler)


def test_bounded_stability_uses_fake_clock_and_finite_attempts(tmp_path):
    spec = pg_spec(tmp_path); clock = FakeClock()
    baseline = parse_restricted_docker_observation(inspect_output(spec), spec)
    fake = stability_fake(spec, [inspect_output(spec), inspect_output(spec)])
    result = observe_lifecycle_stability(
        fake, spec, CID, baseline, window=1.0, interval=0.5,
        monotonic=clock.monotonic, sleeper=clock.sleep)
    assert result["running"] is True and clock.sleeps == [0.5, 0.5]
    assert len([argv for argv, _ in fake.calls if docker_subcommand(argv) == "inspect"]) == 2


@pytest.mark.parametrize("change", ["exited", "cid", "started", "digest", "labels"])
def test_stability_identity_or_state_change_fails_closed(tmp_path, change):
    spec = pg_spec(tmp_path); clock = FakeClock()
    baseline = parse_restricted_docker_observation(inspect_output(spec), spec)
    kwargs = {"running": False} if change == "exited" else \
             {"cid": "d" * 64} if change == "cid" else \
             {"started": "2026-08-16T00:00:01Z"} if change == "started" else \
             {"digest": "sha256:" + "d" * 64} if change == "digest" else {"labels": {}}
    fake = stability_fake(spec, [inspect_output(spec, **kwargs)])
    with pytest.raises((OrchestrationError, ResourceAttestationError)):
        observe_lifecycle_stability(
            fake, spec, CID, baseline, window=1.0, interval=0.5,
            monotonic=clock.monotonic, sleeper=clock.sleep)


def test_stability_listener_disappearance_fails_closed(tmp_path):
    spec = pg_spec(tmp_path); clock = FakeClock()
    baseline = parse_restricted_docker_observation(inspect_output(spec), spec)
    fake = stability_fake(spec, [inspect_output(spec)], listener_fails_after=1)
    with pytest.raises(OrchestrationError) as error:
        observe_lifecycle_stability(
            fake, spec, CID, baseline, window=1.0, interval=0.5,
            monotonic=clock.monotonic, sleeper=clock.sleep)
    assert error.value.category is FailureClass.LISTENER_ATTESTATION_FAILED


def test_immediate_exit_after_first_listener_never_reaches_sentinel(tmp_path):
    spec, fake = fake_success(tmp_path); clock = FakeClock(); inspect_count = 0
    original = fake.handler
    def exit_after_first(argv, kwargs, count):
        nonlocal inspect_count
        if docker_subcommand(argv) == "inspect":
            inspect_count += 1
            return CommandResult(0, inspect_output(spec, running=inspect_count == 1))
        return original(argv, kwargs, count)
    fake.handler = exit_after_first
    with pytest.raises(OrchestrationError):
        provision_fast(spec, executor=fake, approved_root=tmp_path / "approved",
                           secret_factory=lambda: SYNTHETIC_SECRET,
                           stability_window=1.0, stability_interval=0.5,
                           monotonic=clock.monotonic, sleeper=clock.sleep)
    assert not (spec.temp_dir / "sentinel.json").exists()


def test_post_sentinel_exit_never_returns_ready(tmp_path, monkeypatch):
    spec, fake = fake_success(tmp_path); clock = FakeClock(); sentinel_written = False
    original_handler = fake.handler; real_write = flows.write_secure_json
    def tracked_write(path, payload, **kwargs):
        nonlocal sentinel_written
        real_write(path, payload, **kwargs)
        if path.name == "sentinel.json": sentinel_written = True
    def exit_after_sentinel(argv, kwargs, count):
        if docker_subcommand(argv) == "inspect" and sentinel_written:
            return CommandResult(0, inspect_output(spec, running=False))
        return original_handler(argv, kwargs, count)
    monkeypatch.setattr(flows, "write_secure_json", tracked_write)
    fake.handler = exit_after_sentinel
    with pytest.raises(OrchestrationError):
        provision_fast(spec, executor=fake, approved_root=tmp_path / "approved",
                           secret_factory=lambda: SYNTHETIC_SECRET,
                           stability_window=1.0, stability_interval=0.5,
                           monotonic=clock.monotonic, sleeper=clock.sleep)
    assert sentinel_written


def test_redis_post_sentinel_tmpfs_drift_never_returns_ready(tmp_path, monkeypatch):
    spec = redis_spec(tmp_path)
    listener_count = 0
    sentinel_written = False
    real_write = flows.write_secure_json
    def tracked_write(path, payload, **kwargs):
        nonlocal sentinel_written
        real_write(path, payload, **kwargs)
        if path.name == "sentinel.json":
            sentinel_written = True
    def handler(argv, kwargs, _count):
        nonlocal listener_count
        if docker_subcommand(argv) == "ps": return CommandResult(0, "")
        if argv[0].endswith("/ss"):
            listener_count += 1
            return CommandResult(0, "" if listener_count == 1 else
                                 f"LISTEN 0 1 127.0.0.1:{spec.port} 0.0.0.0:*\n")
        if argv[0].endswith("/lsof"):
            return CommandResult(1 if listener_count == 1 else 0, "" if listener_count == 1 else
                                 f"docker-proxy TCP 127.0.0.1:{spec.port} (LISTEN)")
        if argv == spec.argv: return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "start": return CommandResult(0, CID + "\n")
        if docker_subcommand(argv) == "inspect":
            config = ({"/data": "rw,size=1024,mode=0700"} if sentinel_written else None)
            return CommandResult(0, inspect_output(spec, host_tmpfs=config))
        raise AssertionError(argv)
    monkeypatch.setattr(flows, "write_secure_json", tracked_write)
    with pytest.raises(OrchestrationError):
        provision_fast(spec, executor=FakeExecutor(handler),
                       approved_root=tmp_path / "approved")
    assert sentinel_written


def test_ready_semantics_require_both_stability_phases_in_source():
    source = Path(flows.__file__).read_text()
    assert source.index('states.append("STABILITY_OBSERVED")') < source.index('states.append("SENTINEL_WRITTEN")')
    assert source.index('states.append("SENTINEL_WRITTEN")') < source.index('"POST_SENTINEL_OBSERVED", "READY"')


def provision_fast(*args, **kwargs):
    clock = FakeClock()
    kwargs.setdefault("stability_window", 1.0)
    kwargs.setdefault("stability_interval", 0.5)
    kwargs.setdefault("monotonic", clock.monotonic)
    kwargs.setdefault("sleeper", clock.sleep)
    return provision_resource(*args, **kwargs)


def _credential_file(tmp_path, monkeypatch, *, content=SYNTHETIC_SECRET, mode=0o600):
    root = tmp_path / "functional-test"
    run = root / RUN_ID
    root.mkdir(mode=0o700)
    run.mkdir(mode=0o700)
    monkeypatch.setattr(lifecycle, "FUNCTIONAL_TEST_STATE_ROOT", root)
    path = lifecycle.postgres_password_file_path(RUN_ID)
    path.write_bytes(content if isinstance(content, bytes) else content.encode("ascii"))
    path.chmod(mode)
    return path


def test_postgres_password_file_valid_exact_metadata(tmp_path, monkeypatch):
    path = _credential_file(tmp_path, monkeypatch)
    assert read_postgres_password_file(path, run_id=RUN_ID) == SYNTHETIC_SECRET


def test_postgres_password_file_missing_rejected(tmp_path, monkeypatch):
    path = _credential_file(tmp_path, monkeypatch)
    path.unlink()
    with pytest.raises(ResourceAttestationError, match="unavailable"):
        read_postgres_password_file(path, run_id=RUN_ID)


def test_postgres_password_file_symlink_rejected(tmp_path, monkeypatch):
    path = _credential_file(tmp_path, monkeypatch)
    target = path.with_name("target")
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ResourceAttestationError):
        read_postgres_password_file(path, run_id=RUN_ID)


def test_postgres_password_directory_rejected(tmp_path, monkeypatch):
    path = _credential_file(tmp_path, monkeypatch)
    path.unlink()
    path.mkdir(mode=0o600)
    with pytest.raises(ResourceAttestationError, match="metadata"):
        read_postgres_password_file(path, run_id=RUN_ID)


@pytest.mark.parametrize("mode", [0o644, 0o400])
def test_postgres_password_file_exact_mode_required(tmp_path, monkeypatch, mode):
    path = _credential_file(tmp_path, monkeypatch, mode=mode)
    with pytest.raises(ResourceAttestationError, match="metadata"):
        read_postgres_password_file(path, run_id=RUN_ID)


@pytest.mark.parametrize("identity", [(100000, None), (None, 100000)])
def test_postgres_password_file_exact_owner_required(tmp_path, monkeypatch, identity):
    path = _credential_file(tmp_path, monkeypatch)
    uid, gid = identity
    current_uid, current_gid = lifecycle.lifecycle_operator_identity()
    monkeypatch.setattr(lifecycle, "lifecycle_operator_identity",
                        lambda: (uid if uid is not None else current_uid,
                                 gid if gid is not None else current_gid))
    with pytest.raises(ResourceAttestationError, match="metadata"):
        read_postgres_password_file(path, run_id=RUN_ID)


@pytest.mark.parametrize("content", [b"", b"S" * 44, b"S" * 42 + b"\n",
                                     b"S" * 42 + b"\x00", b"S" * 42 + b"!"])
def test_postgres_password_file_invalid_content_rejected(tmp_path, monkeypatch, content):
    path = _credential_file(tmp_path, monkeypatch, content=content)
    with pytest.raises(ResourceAttestationError):
        read_postgres_password_file(path, run_id=RUN_ID)


@pytest.mark.parametrize("candidate", [
    Path("/opt/MarketingOSAI/postgres-password"),
    Path(__file__).resolve(),
    Path("/home/cbemsadmin/postgres-password"),
])
def test_postgres_password_file_unapproved_path_rejected(candidate):
    with pytest.raises(ResourceAttestationError, match="path invalid"):
        read_postgres_password_file(candidate, run_id=RUN_ID)


def test_postgres_password_file_uses_nofollow_and_fstat(tmp_path, monkeypatch):
    path = _credential_file(tmp_path, monkeypatch)
    real_open, observed = lifecycle.os.open, {}
    def tracked_open(value, flags):
        observed["flags"] = flags
        return real_open(value, flags)
    monkeypatch.setattr(lifecycle.os, "open", tracked_open)
    assert read_postgres_password_file(path, run_id=RUN_ID) == SYNTHETIC_SECRET
    if hasattr(lifecycle.os, "O_NOFOLLOW"):
        assert observed["flags"] & lifecycle.os.O_NOFOLLOW


def test_postgres_cli_requires_password_file_and_redis_rejects_it(monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/provision_integration_resources_cleanroom.py"
    base = [str(script), "postgres", "--image", PG_IMAGE, "--port", "15432",
            "--run-id", RUN_ID]
    monkeypatch.setattr(sys, "argv", base)
    with pytest.raises(SystemExit, match="requires --postgres-password-file"):
        runpy.run_path(str(script), run_name="__main__")
    monkeypatch.setattr(sys, "argv", [str(script), "redis", "--image", REDIS_IMAGE,
        "--port", "16379", "--run-id", RUN_ID, "--postgres-password-file",
        str(postgres_password_file_path(RUN_ID))])
    with pytest.raises(SystemExit, match="Redis does not accept"):
        runpy.run_path(str(script), run_name="__main__")


def test_postgres_execute_reads_same_secret_without_output(tmp_path, monkeypatch, capsys):
    path = _credential_file(tmp_path, monkeypatch)
    script = Path(__file__).resolve().parents[2] / "scripts/provision_integration_resources_cleanroom.py"
    captured = {}
    def fake_provision(spec, *, executor, secret_factory):
        captured["password"] = secret_factory()
        return {"state": "READY", "container_id": CID, "secret_logged": False}
    monkeypatch.setattr(flows, "provision_resource", fake_provision)
    monkeypatch.setattr("_integration_execute_flows.provision_resource", fake_provision)
    monkeypatch.setattr("_integration_execute_orchestration.SubprocessCommandExecutor", lambda: object())
    monkeypatch.setattr(sys, "argv", [str(script), "postgres", "--image", PG_IMAGE,
        "--port", "15432", "--run-id", RUN_ID, "--postgres-password-file",
        str(path), "--execute"])
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(script), run_name="__main__")
    assert result.value.code == 0
    assert captured["password"] == SYNTHETIC_SECRET
    output = capsys.readouterr().out
    assert SYNTHETIC_SECRET not in output and "READY" in output


def test_password_file_contract_has_no_plaintext_cli_and_preserves_env_rejection():
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/provision_integration_resources_cleanroom.py").read_text()
    flow = Path(flows.__file__).read_text()
    assert "--postgres-password-file" in script
    assert "--postgres-password=" not in script
    assert "POSTGRES_TEST_PASSWORD" in flow and "POSTGRES_PASSWORD" in flow
    assert "EXTERNAL_POSTGRES_SECRET_FORBIDDEN" in flow

# R22 COMMIT16 RED PHASE — POSTGRES DOCKER SECRET TRANSPORT


def test_postgres_secret_transport_red_spec_uses_run_scoped_env_file(tmp_path):
    spec = pg_spec(tmp_path)

    expected_transport = spec.temp_dir / "postgres-docker.env"

    assert "--env-file" in spec.argv, (
        "RED_EXPECTED: PostgreSQL create must use --env-file"
    )

    index = spec.argv.index("--env-file")
    assert index + 1 < len(spec.argv)
    assert spec.argv[index + 1] == str(expected_transport)

    assert "POSTGRES_PASSWORD" not in spec.argv
    assert not any(
        isinstance(token, str) and token.startswith("POSTGRES_PASSWORD=")
        for token in spec.argv
    )



def test_postgres_secret_transport_red_create_child_env_has_no_password(tmp_path):
    spec, fake = fake_success(tmp_path)

    provision_fast(
        spec,
        executor=fake,
        approved_root=tmp_path / "approved",
        secret_factory=lambda: SYNTHETIC_SECRET,
    )

    create_calls = [
        (argv, kwargs)
        for argv, kwargs in fake.calls
        if argv == spec.argv
    ]

    assert len(create_calls) == 1

    _argv, kwargs = create_calls[0]
    child_env = kwargs.get("env", {})

    assert "POSTGRES_PASSWORD" not in child_env, (
        "RED_EXPECTED: password must not cross sudo through subprocess env"
    )
    assert set(child_env) == {"PATH", "LANG"}


def test_postgres_secret_transport_red_policy_accepts_exact_run_scoped_env_file(tmp_path):
    spec = pg_spec(tmp_path)

    assert "--env-file" in spec.argv

    env_file_index = spec.argv.index("--env-file")
    assert spec.argv[env_file_index + 1] == str(
        spec.temp_dir / "postgres-docker.env"
    )

    assert docker_subcommand(spec.argv) == "create", (
        "Docker policy must accept the exact run-scoped "
        "PostgreSQL env-file transport"
    )

    wrong_path = list(spec.argv)
    wrong_path[env_file_index + 1] = str(
        spec.temp_dir / "unexpected.env"
    )

    assert docker_subcommand(tuple(wrong_path)) is None, (
        "Docker policy must reject any non-exact env-file path"
    )

# R22 COMMIT16 PHASE3C — TRANSPORT FAILURE PATHS


def test_ambiguous_create_exception_removes_transport_before_preserve(tmp_path):
    spec, fake = fake_success(tmp_path)
    original = fake.handler

    def handler(argv, kwargs, count):
        if argv == spec.argv:
            raise RuntimeError(
                "synthetic-create-exception"
            )

        return original(
            argv,
            kwargs,
            count,
        )

    fake.handler = handler

    with pytest.raises(OrchestrationError) as error:
        provision_fast(
            spec,
            executor=fake,
            approved_root=tmp_path / "approved",
            secret_factory=lambda: SYNTHETIC_SECRET,
        )

    assert (
        error.value.category
        is FailureClass.PROVISION_FAILED_REVIEW_REQUIRED
    )
    assert (
        error.value.original_category
        is FailureClass.CREATE_FAILED
    )
    assert (
        error.value.ownership_boundary
        == "CREATE_AMBIGUOUS_PRESERVE"
    )
    assert error.value.resource_preserved is True

    transport = spec.temp_dir / "postgres-docker.env"

    assert not transport.exists()
    assert not any(
        candidate.name.startswith(
            ".postgres-docker.env."
        )
        for candidate in spec.temp_dir.iterdir()
    )

    assert SYNTHETIC_SECRET not in str(error.value)


def test_nonzero_create_result_removes_transport_before_preserve(tmp_path):
    spec, fake = fake_success(tmp_path)
    original = fake.handler

    def handler(argv, kwargs, count):
        if argv == spec.argv:
            return CommandResult(
                1,
                "",
            )

        return original(
            argv,
            kwargs,
            count,
        )

    fake.handler = handler

    with pytest.raises(OrchestrationError) as error:
        provision_fast(
            spec,
            executor=fake,
            approved_root=tmp_path / "approved",
            secret_factory=lambda: SYNTHETIC_SECRET,
        )

    assert (
        error.value.category
        is FailureClass.PROVISION_FAILED_REVIEW_REQUIRED
    )
    assert (
        error.value.original_category
        is FailureClass.CREATE_FAILED
    )
    assert (
        error.value.ownership_boundary
        == "CREATE_AMBIGUOUS_PRESERVE"
    )

    transport = spec.temp_dir / "postgres-docker.env"

    assert not transport.exists()
    assert not any(
        candidate.name.startswith(
            ".postgres-docker.env."
        )
        for candidate in spec.temp_dir.iterdir()
    )

    assert SYNTHETIC_SECRET not in str(error.value)


def test_redis_docker_policy_rejects_any_env_file(tmp_path):
    spec = redis_spec(tmp_path)

    candidate = list(spec.argv)
    image_index = candidate.index(spec.image)

    candidate[image_index:image_index] = [
        "--env-file",
        str(
            spec.temp_dir
            / "postgres-docker.env"
        ),
    ]

    assert docker_subcommand(
        tuple(candidate)
    ) is None


def test_postgres_execute_leaves_operator_password_file_unchanged(
        tmp_path, monkeypatch):
    password_path = _credential_file(
        tmp_path,
        monkeypatch,
    )

    before_bytes = password_path.read_bytes()
    before_mode = (
        password_path.stat(follow_symlinks=False).st_mode
        & 0o777
    )

    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "provision_integration_resources_cleanroom.py"
    )

    def fake_provision(spec, *, executor, secret_factory):
        assert secret_factory() == SYNTHETIC_SECRET

        return {
            "state": "READY",
            "container_id": CID,
            "secret_logged": False,
        }

    monkeypatch.setattr(
        flows,
        "provision_resource",
        fake_provision,
    )
    monkeypatch.setattr(
        "_integration_execute_flows.provision_resource",
        fake_provision,
    )
    monkeypatch.setattr(
        "_integration_execute_orchestration.SubprocessCommandExecutor",
        lambda: object(),
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "postgres",
            "--image",
            PG_IMAGE,
            "--port",
            "15432",
            "--run-id",
            RUN_ID,
            "--postgres-password-file",
            str(password_path),
            "--execute",
        ],
    )

    with pytest.raises(SystemExit) as result:
        runpy.run_path(
            str(script),
            run_name="__main__",
        )

    assert result.value.code == 0
    assert password_path.read_bytes() == before_bytes
    assert (
        password_path.stat(
            follow_symlinks=False
        ).st_mode
        & 0o777
    ) == before_mode
    assert before_mode == 0o600


def test_inspect_template_is_missing_key_safe_for_hostconfig_tmpfs():
    """HostConfig may omit Tmpfs; restricted Docker observation must still execute."""
    import _integration_execute_orchestration as orchestration

    argv = orchestration._inspect_argv(CID)

    assert docker_subcommand(argv) == "inspect"

    assert argv[:7] == (
        *DOCKER_PRIVILEGE_PREFIX,
        "inspect",
        "--type",
        "container",
        "--format",
    )

    assert argv[8] == CID

    fields = argv[7].split("\n")

    assert len(fields) == 11

    assert tuple(fields[:9]) == (
        "{{json .Id}}",
        "{{json .Name}}",
        "{{json .Config.Image}}",
        "{{json .Config.Labels}}",
        "{{json .State.Running}}",
        "{{json .State.StartedAt}}",
        "{{json .HostConfig.NetworkMode}}",
        "{{json .NetworkSettings.Ports}}",
        "{{json .Mounts}}",
    )

    expected_tmpfs_field = (
        '{{if (index .HostConfig "Tmpfs")}}'
        '{{json (index .HostConfig "Tmpfs")}}'
        '{{else}}{}{{end}}'
    )

    assert fields[9] == expected_tmpfs_field

    assert fields[10] == "{{json .Config.Volumes}}"

    # The unsafe direct map-key lookup is the regression being blocked.
    assert "{{json .HostConfig.Tmpfs}}" not in argv[7]

    # Restricted observation remains secret-blind.
    assert ".Config.Env" not in argv[7]
    assert "POSTGRES_PASSWORD" not in argv[7]
    assert "POSTGRES_TEST_PASSWORD" not in argv[7]
