"""Provision, migration, and teardown flows built on restricted executors."""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import shutil
import sys
import time
from typing import Callable

from _integration_execute_orchestration import (
    CommandExecutor, FailureClass, OrchestrationError, DOCKER, _child_env,
    _inspect_argv, collect_docker_observation, collect_inventory,
    observe_lifecycle_stability,
    observe_listener, provisional_rollback, reject_inventory_collision,
    require_loopback_listener, require_port_free, validate_provisional_observation,
)
from _integration_resource_attestation import (
    ALEMBIC_TARGET_HEAD, APPROVED_TEMP_ROOT, CONTAINER_ID_PATTERN,
    load_sentinel, reconstruct_database_url, validate_migration_gate,
)
from _integration_resource_lifecycle import (
    DockerResourceSpec, build_docker_spec, create_resource_directories,
    normalize_docker_observation, sanitized_subprocess_environment,
    require_empty_postgres_data_dir,
    sentinel_payload, validate_cleanup_path, write_secure_json,
)


def provision_resource(spec: DockerResourceSpec, *, executor: CommandExecutor,
                       approved_root: Path = APPROVED_TEMP_ROOT,
                       secret_factory: Callable[[], str] | None = None,
                       stability_window: float = 2.0,
                       stability_interval: float = 0.5,
                       monotonic: Callable[[], float] = time.monotonic,
                       sleeper: Callable[[float], None] = time.sleep,
                       ) -> dict[str, object]:
    states = ["PRECHECK"]
    if spec.resource_type == "postgres" and any(
            name in os.environ for name in ("POSTGRES_TEST_PASSWORD", "POSTGRES_PASSWORD")):
        raise OrchestrationError(FailureClass.EXTERNAL_POSTGRES_SECRET_FORBIDDEN)
    reject_inventory_collision(collect_inventory(executor), spec)
    create_resource_directories(spec.run_id, spec.resource_type, approved_root)
    states.append("TEMP_ROOT_CREATED")
    if spec.resource_type == "postgres":
        states.append("PGDATA_CREATED")
        try:
            require_empty_postgres_data_dir(spec)
        except Exception:
            raise OrchestrationError(FailureClass.PGDATA_NOT_EMPTY) from None
        states.append("PGDATA_EMPTY_VERIFIED")
    require_port_free(observe_listener(executor, spec.port)); states.append("PRE_PORT_FREE")
    child_environment = _child_env()
    generated_secret = ""
    if spec.resource_type == "postgres":
        try:
            generated_secret = (secret_factory or (lambda: secrets.token_urlsafe(32)))()
        except Exception:
            raise OrchestrationError(FailureClass.SECRET_GENERATION_FAILED) from None
        if (not isinstance(generated_secret, str) or len(generated_secret) < 43 or
                not generated_secret.isascii()):
            raise OrchestrationError(FailureClass.SECRET_GENERATION_FAILED)
        child_environment = _child_env({"POSTGRES_PASSWORD": generated_secret})
    try:
        created = executor.run(spec.argv, env=child_environment)
    except Exception:
        raise OrchestrationError(FailureClass.CREATE_FAILED) from None
    finally:
        child_environment.pop("POSTGRES_PASSWORD", None)
        generated_secret = ""
    container_id = created.stdout.strip()
    if not CONTAINER_ID_PATTERN.fullmatch(container_id):
        raise OrchestrationError(FailureClass.CREATE_FAILED)
    states.extend(("CONTAINER_CREATED", "EXACT_CONTAINER_ID_CAPTURED"))
    try:
        try:
            executor.run((DOCKER, "start", container_id), env=_child_env())
        except Exception:
            raise OrchestrationError(FailureClass.START_FAILED) from None
        states.append("CONTAINER_STARTED")
        raw = collect_docker_observation(executor, spec, container_id); states.append("DOCKER_OBSERVED")
        validate_provisional_observation(raw, spec, container_id)
        require_loopback_listener(observe_listener(executor, spec.port)); states.append("LISTENER_OBSERVED")
        stable = observe_lifecycle_stability(
            executor, spec, container_id, raw, window=stability_window,
            interval=stability_interval, monotonic=monotonic, sleeper=sleeper,
        ); states.append("STABILITY_OBSERVED")
        observation = normalize_docker_observation(stable, spec); states.append("ATTESTED")
        write_secure_json(spec.temp_dir / "observation.json", observation, approved_root=approved_root)
        write_secure_json(spec.temp_dir / "sentinel.json", sentinel_payload(observation), approved_root=approved_root)
        states.append("SENTINEL_WRITTEN")
        final_raw = collect_docker_observation(executor, spec, container_id)
        validate_provisional_observation(final_raw, spec, container_id)
        final = normalize_docker_observation(final_raw, spec)
        require_loopback_listener(observe_listener(executor, spec.port))
        if (final_raw.get("started_at") != stable.get("started_at") or
                sentinel_payload(final) != sentinel_payload(observation)):
            raise OrchestrationError(FailureClass.LIFECYCLE_STABILITY_FAILED)
        states.extend(("POST_SENTINEL_OBSERVED", "READY"))
    except OrchestrationError as original:
        provisional_rollback(executor, spec, container_id)
        raise original
    except Exception:
        try:
            provisional_rollback(executor, spec, container_id)
        except OrchestrationError:
            raise
        raise OrchestrationError(FailureClass.SENTINEL_WRITE_FAILED,
                                 resource_preserved=False) from None
    return {"state": states[-1], "states": tuple(states), "container_id": container_id,
            "sentinel": str(spec.temp_dir / "sentinel.json"), "secret_logged": False}


def build_migration_execution(*, sentinel_path: Path, run_id: str, image: str,
                              runtime_password: str, executor: CommandExecutor,
                              approved_root: Path = APPROVED_TEMP_ROOT):
    attested = load_sentinel(sentinel_path, expected_run_id=run_id,
                             expected_type="postgres", approved_root=approved_root)
    spec = build_docker_spec(run_id=run_id, resource_type="postgres", image=image,
                             port=attested.resource_port, approved_root=approved_root)
    if spec.image_digest != attested.resource_image_digest or not attested.resource_container_id:
        raise OrchestrationError(FailureClass.MIGRATION_AUTHORIZATION_FAILED)
    observation = normalize_docker_observation(
        collect_docker_observation(executor, spec, attested.resource_container_id), spec)
    require_loopback_listener(observe_listener(executor, spec.port))
    database_url = reconstruct_database_url(attested, runtime_password)
    observation_path = spec.temp_dir / "migration-observation.json"
    write_secure_json(observation_path, observation, approved_root=approved_root)
    env = sanitized_subprocess_environment({
        "DATABASE_URL": database_url,
        "ENVIRONMENT": "test", "MARKETINGOS_TEST_MODE": "integration",
        "MARKETINGOS_TEST_RESOURCE_SCOPE": "disposable", "TEST_RUN_ID": run_id,
    })
    validate_migration_gate(attested, observation_path, requested_head=ALEMBIC_TARGET_HEAD,
                            approved_root=approved_root, environment=env)
    return ((sys.executable, "-m", "alembic", "upgrade", ALEMBIC_TARGET_HEAD),
            env, Path(__file__).resolve().parents[1])


def execute_migration(**kwargs) -> None:
    executor = kwargs["executor"]
    argv, env, cwd = build_migration_execution(**kwargs)
    try:
        executor.run(argv, env=env, cwd=cwd)
    except Exception:
        raise OrchestrationError(FailureClass.MIGRATION_EXECUTION_FAILED) from None


def remove_exact_temp_path(path: Path, *, run_id: str, resource_type: str,
                           approved_root: Path = APPROVED_TEMP_ROOT) -> None:
    exact = validate_cleanup_path(path, run_id=run_id, resource_type=resource_type,
                                  approved_root=approved_root)
    for entry in list(os.scandir(exact)):
        candidate = Path(entry.path)
        if entry.is_symlink():
            raise OrchestrationError(FailureClass.TEARDOWN_AUTHORIZATION_FAILED)
        if entry.is_dir(follow_symlinks=False):
            shutil.rmtree(candidate)
        else:
            candidate.unlink()
    exact.rmdir()


def teardown_resource(*, sentinel_path: Path, run_id: str, resource_type: str,
                      image: str, executor: CommandExecutor,
                      approved_root: Path = APPROVED_TEMP_ROOT) -> dict[str, object]:
    attested = load_sentinel(sentinel_path, expected_run_id=run_id,
                             expected_type=resource_type, approved_root=approved_root)
    if not attested.resource_container_id:
        raise OrchestrationError(FailureClass.TEARDOWN_AUTHORIZATION_FAILED)
    spec = build_docker_spec(run_id=run_id, resource_type=resource_type, image=image,
                             port=attested.resource_port, redis_db=attested.redis_db or 15,
                             approved_root=approved_root)
    observation = normalize_docker_observation(
        collect_docker_observation(executor, spec, attested.resource_container_id), spec)
    require_loopback_listener(observe_listener(executor, spec.port))
    expected = dict(attested.__dict__)
    expected["resource_temp_dir"] = str(attested.resource_temp_dir)
    if sentinel_payload(observation) != sentinel_payload(expected):
        raise OrchestrationError(FailureClass.TEARDOWN_AUTHORIZATION_FAILED)
    exact = attested.resource_container_id
    try:
        executor.run((DOCKER, "stop", exact), env=_child_env())
        executor.run((DOCKER, "rm", exact), env=_child_env())
        absent = executor.run(_inspect_argv(exact), env=_child_env(),
                              allowed_returncodes=frozenset({1}))
        if absent.returncode != 1:
            raise OrchestrationError(FailureClass.TEARDOWN_EXECUTION_FAILED)
        require_port_free(observe_listener(executor, spec.port))
        remove_exact_temp_path(spec.temp_dir, run_id=run_id,
                               resource_type=resource_type, approved_root=approved_root)
    except OrchestrationError:
        raise
    except Exception:
        raise OrchestrationError(FailureClass.TEARDOWN_EXECUTION_FAILED) from None
    return {"state": "COMPLETE", "container_id": exact,
            "path_absent": not spec.temp_dir.exists()}


def assert_same_run_resources(postgres_run_id: str, redis_run_id: str | None,
                              *, redis_required: bool) -> None:
    if redis_required and redis_run_id != postgres_run_id:
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
    if not redis_required and redis_run_id is not None:
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
