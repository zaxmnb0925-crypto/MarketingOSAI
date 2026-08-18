"""Fail-closed execute orchestration for disposable integration resources.

Importing this module performs no command. Real commands are reachable only
through an explicitly supplied executor, replaced by fakes in safety tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import sys
from typing import Mapping, Protocol, Sequence

from _integration_docker_command import (
    docker_command, is_privileged_docker_command,
)
from _integration_resource_attestation import (
    ALEMBIC_TARGET_HEAD, APPROVED_TEMP_ROOT, CONTAINER_ID_PATTERN,
    ResourceAttestationError, load_sentinel, reconstruct_database_url,
    validate_candidate_port, validate_migration_gate,
)
from _integration_resource_lifecycle import (
    DockerResourceSpec, build_docker_spec, create_resource_directories,
    normalize_docker_observation, sanitized_subprocess_environment,
    sentinel_payload, validate_cleanup_path, write_secure_json,
)

MAX_CAPTURE_BYTES = 256 * 1024
DEFAULT_TIMEOUT = 30.0
SS, LSOF = "/usr/bin/ss", "/usr/bin/lsof"


class FailureClass(str, Enum):
    PORT_COLLISION = "PORT_COLLISION"
    CREATE_FAILED = "CREATE_FAILED"
    START_FAILED = "START_FAILED"
    DOCKER_OBSERVATION_FAILED = "DOCKER_OBSERVATION_FAILED"
    LISTENER_ATTESTATION_FAILED = "LISTENER_ATTESTATION_FAILED"
    RESOURCE_IDENTITY_MISMATCH = "RESOURCE_IDENTITY_MISMATCH"
    SENTINEL_WRITE_FAILED = "SENTINEL_WRITE_FAILED"
    INVENTORY_COLLISION = "INVENTORY_COLLISION"
    EXTERNAL_POSTGRES_SECRET_FORBIDDEN = "EXTERNAL_POSTGRES_SECRET_FORBIDDEN"
    SECRET_GENERATION_FAILED = "SECRET_GENERATION_FAILED"
    PROVISION_FAILED_REVIEW_REQUIRED = "PROVISION_FAILED_REVIEW_REQUIRED"
    MIGRATION_AUTHORIZATION_FAILED = "MIGRATION_AUTHORIZATION_FAILED"
    MIGRATION_EXECUTION_FAILED = "MIGRATION_EXECUTION_FAILED"
    LIFECYCLE_STABILITY_FAILED = "LIFECYCLE_STABILITY_FAILED"
    PGDATA_NOT_EMPTY = "PGDATA_NOT_EMPTY"
    TEARDOWN_AUTHORIZATION_FAILED = "TEARDOWN_AUTHORIZATION_FAILED"
    TEARDOWN_EXECUTION_FAILED = "TEARDOWN_EXECUTION_FAILED"


class OrchestrationError(RuntimeError):
    def __init__(self, category: FailureClass, *, resource_preserved: bool = True,
                 ownership_boundary: str | None = None,
                 original_category: FailureClass | None = None):
        self.category, self.resource_preserved = category, resource_preserved
        self.ownership_boundary = ownership_boundary
        self.original_category = original_category
        super().__init__(category.value)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandExecutor(Protocol):
    def run(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None,
            cwd: Path | None = None, timeout: float = DEFAULT_TIMEOUT,
            allowed_returncodes: frozenset[int] = frozenset({0})) -> CommandResult: ...


class SubprocessCommandExecutor:
    """Bounded argv-only subprocess implementation; never logs raw output."""
    _UNPRIVILEGED_EXECUTABLES = {SS, LSOF, sys.executable}

    def run(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None,
            cwd: Path | None = None, timeout: float = DEFAULT_TIMEOUT,
            allowed_returncodes: frozenset[int] = frozenset({0})) -> CommandResult:
        command = tuple(argv)
        if (not command or any(not isinstance(value, str) for value in command) or
                (not is_privileged_docker_command(command) and
                 command[0] not in self._UNPRIVILEGED_EXECUTABLES)):
            raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
        try:
            completed = subprocess.run(
                command, shell=False, cwd=cwd,
                env=dict(env or {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}),
                text=True, capture_output=True, timeout=timeout, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED) from None
        result = CommandResult(completed.returncode,
                               completed.stdout[:MAX_CAPTURE_BYTES],
                               completed.stderr[:MAX_CAPTURE_BYTES])
        if result.returncode not in allowed_returncodes:
            raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED)
        return result


@dataclass(frozen=True)
class InventoryItem:
    container_id: str
    name: str
    test_resource: str
    run_id: str
    resource_type: str


@dataclass(frozen=True)
class ListenerObservation:
    host: str
    port: int
    ss_output: str
    lsof_output: str


def _child_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    return sanitized_subprocess_environment(dict(extra or {}))


def collect_inventory(executor: CommandExecutor) -> tuple[InventoryItem, ...]:
    inventory_format = "\t".join((
        "{{.ID}}",
        "{{.Names}}",
        '{{.Label "com.marketingos.test-resource"}}',
        '{{.Label "com.marketingos.test-run-id"}}',
        '{{.Label "com.marketingos.test-resource-type"}}',
    ))
    result = executor.run(
        docker_command("ps", "-a", "--no-trunc", "--format", inventory_format),
        env=_child_env(),
    )
    items = []
    if not result.stdout:
        return ()
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 5:
            raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED)
        container_id, name, test_resource, run_id, resource_type = fields
        if (not CONTAINER_ID_PATTERN.fullmatch(container_id) or
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", name) or
                any(not re.fullmatch(r"[A-Za-z0-9_.:-]{0,128}", value)
                    for value in (test_resource, run_id, resource_type))):
            raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED)
        items.append(InventoryItem(
            container_id, name, test_resource, run_id, resource_type,
        ))
    return tuple(items)


def reject_inventory_collision(items: Sequence[InventoryItem], spec: DockerResourceSpec) -> None:
    for item in items:
        if not isinstance(item.name, str) or not isinstance(item.run_id, str):
            raise OrchestrationError(FailureClass.INVENTORY_COLLISION)
        if item.name == spec.container_name or item.run_id == spec.run_id:
            raise OrchestrationError(FailureClass.INVENTORY_COLLISION)


def _inspect_argv(container_id: str) -> tuple[str, ...]:
    if not CONTAINER_ID_PATTERN.fullmatch(container_id):
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
    fields = ("{{json .Id}}", "{{json .Name}}", "{{json .Config.Image}}",
              "{{json .Config.Labels}}", "{{json .State.Running}}",
              "{{json .State.StartedAt}}", "{{json .HostConfig.NetworkMode}}",
              "{{json .NetworkSettings.Ports}}", "{{json .Mounts}}",
              '{{if (index .HostConfig "Tmpfs")}}{{json (index .HostConfig "Tmpfs")}}{{else}}{}{{end}}', "{{json .Config.Volumes}}")
    return docker_command("inspect", "--type", "container", "--format",
                          "\n".join(fields), container_id)


def parse_restricted_docker_observation(output: str, spec: DockerResourceSpec) -> dict[str, object]:
    lines = output.splitlines()
    if len(lines) != 11:
        raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED)
    try:
        (cid, name, image, labels, running, started, network, ports, mounts,
         host_tmpfs, declared_volumes) = (json.loads(line) for line in lines)
        binding = ports[f"{spec.internal_port}/tcp"]
        if not isinstance(binding, list) or len(binding) != 1:
            raise ValueError
        mount_details = [{
            "type": entry["Type"], "source": entry.get("Source", ""),
            "destination": entry["Destination"], "rw": entry["RW"],
        } for entry in mounts]
        sources = [entry["source"] for entry in mount_details if entry["source"]]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED) from None
    return {"container_id": cid, "container_name": str(name).removeprefix("/"),
            "image_digest": str(image).rsplit("@", 1)[-1], "labels": {key: labels.get(key) for key in spec.labels},
            "running": running, "started_at": started, "networks": [network],
            "published_host": binding[0]["HostIp"],
            "published_port": int(binding[0]["HostPort"]),
            "internal_port": spec.internal_port, "mount_sources": sources,
            "mount_details": mount_details, "host_tmpfs": host_tmpfs,
            "declared_volumes": declared_volumes}


def collect_docker_observation(executor: CommandExecutor, spec: DockerResourceSpec,
                               container_id: str) -> dict[str, object]:
    result = executor.run(_inspect_argv(container_id), env=_child_env())
    return parse_restricted_docker_observation(result.stdout, spec)


def validate_provisional_observation(raw: Mapping[str, object], spec: DockerResourceSpec,
                                     container_id: str) -> None:
    expected = {"container_id": container_id, "container_name": spec.container_name,
                "image_digest": spec.image_digest, "labels": dict(spec.labels),
                "published_host": "127.0.0.1", "published_port": spec.port,
                "internal_port": spec.internal_port, "networks": ["bridge"],
                "mount_sources": [str(spec.pgdata_dir)] if spec.resource_type == "postgres" else [],
                "mount_details": ([{
                    "type": "bind", "source": str(spec.pgdata_dir),
                    "destination": "/var/lib/postgresql/data", "rw": True,
                }] if spec.resource_type == "postgres" else []),}
    if any(raw.get(key) != value for key, value in expected.items()):
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
    try:
        normalization_candidate = dict(raw)
        normalization_candidate["running"] = True
        normalize_docker_observation(normalization_candidate, spec)
    except Exception:
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH) from None


def observe_lifecycle_stability(
    executor: CommandExecutor, spec: DockerResourceSpec, container_id: str,
    baseline: Mapping[str, object], *, window: float = 2.0, interval: float = 0.5,
    monotonic=time.monotonic, sleeper=time.sleep,
) -> dict[str, object]:
    """Require exact identity and listener throughout a bounded stability window.

    This detects immediate-exit races. It does not claim PostgreSQL application
    readiness and deliberately performs no database query or docker exec.
    """
    if window <= 0 or interval <= 0 or interval > window:
        raise OrchestrationError(FailureClass.LIFECYCLE_STABILITY_FAILED)
    deadline = monotonic() + window
    expected_start = baseline.get("started_at")
    latest = dict(baseline)
    attempts = 0
    max_attempts = int(window / interval) + 2
    while True:
        if (latest.get("started_at") != expected_start or
                latest.get("running") is not True):
            raise OrchestrationError(FailureClass.LIFECYCLE_STABILITY_FAILED)
        validate_provisional_observation(latest, spec, container_id)
        normalize_docker_observation(latest, spec)
        require_loopback_listener(observe_listener(executor, spec.port))
        attempts += 1
        now = monotonic()
        if now >= deadline:
            return latest
        if attempts >= max_attempts:
            raise OrchestrationError(FailureClass.LIFECYCLE_STABILITY_FAILED)
        sleeper(min(interval, deadline - now))
        latest = collect_docker_observation(executor, spec, container_id)


def observe_listener(executor: CommandExecutor, port: int) -> ListenerObservation:
    ss = executor.run((SS, "-ltnH", f"sport = :{port}"), env=_child_env())
    lsof = executor.run((LSOF, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"), env=_child_env(),
                        allowed_returncodes=frozenset({0, 1}))
    host = ""
    for line in ss.stdout.splitlines():
        fields = line.split()
        endpoint = fields[3] if len(fields) >= 4 else ""
        if endpoint.endswith(f":{port}"):
            host = endpoint.rsplit(":", 1)[0].strip("[]")
            break
    return ListenerObservation(host, port, ss.stdout, lsof.stdout)


def require_port_free(value: ListenerObservation) -> None:
    try:
        validate_candidate_port(value.port, ss_listener_output=value.ss_output,
                                lsof_listener_output=value.lsof_output)
    except ResourceAttestationError:
        raise OrchestrationError(FailureClass.PORT_COLLISION) from None


def require_loopback_listener(value: ListenerObservation) -> None:
    if value.host not in {"127.0.0.1", "::1"}:
        raise OrchestrationError(FailureClass.LISTENER_ATTESTATION_FAILED)
    if value.lsof_output and f":{value.port}" not in value.lsof_output:
        raise OrchestrationError(FailureClass.LISTENER_ATTESTATION_FAILED)
