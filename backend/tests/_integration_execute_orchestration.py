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
import shutil
import subprocess
import sys
from typing import Mapping, Protocol, Sequence

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
DOCKER, SS, LSOF = "/usr/bin/docker", "/usr/bin/ss", "/usr/bin/lsof"


class FailureClass(str, Enum):
    PORT_COLLISION = "PORT_COLLISION"
    CREATE_FAILED = "CREATE_FAILED"
    START_FAILED = "START_FAILED"
    DOCKER_OBSERVATION_FAILED = "DOCKER_OBSERVATION_FAILED"
    LISTENER_ATTESTATION_FAILED = "LISTENER_ATTESTATION_FAILED"
    RESOURCE_IDENTITY_MISMATCH = "RESOURCE_IDENTITY_MISMATCH"
    SENTINEL_WRITE_FAILED = "SENTINEL_WRITE_FAILED"
    ROLLBACK_AUTHORIZATION_FAILED = "ROLLBACK_AUTHORIZATION_FAILED"
    ROLLBACK_EXECUTION_FAILED = "ROLLBACK_EXECUTION_FAILED"
    INVENTORY_COLLISION = "INVENTORY_COLLISION"
    MIGRATION_AUTHORIZATION_FAILED = "MIGRATION_AUTHORIZATION_FAILED"
    MIGRATION_EXECUTION_FAILED = "MIGRATION_EXECUTION_FAILED"
    TEARDOWN_AUTHORIZATION_FAILED = "TEARDOWN_AUTHORIZATION_FAILED"
    TEARDOWN_EXECUTION_FAILED = "TEARDOWN_EXECUTION_FAILED"


class OrchestrationError(RuntimeError):
    def __init__(self, category: FailureClass, *, resource_preserved: bool = True):
        self.category, self.resource_preserved = category, resource_preserved
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
    _EXECUTABLES = {DOCKER, SS, LSOF, sys.executable}

    def run(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None,
            cwd: Path | None = None, timeout: float = DEFAULT_TIMEOUT,
            allowed_returncodes: frozenset[int] = frozenset({0})) -> CommandResult:
        command = tuple(argv)
        if not command or command[0] not in self._EXECUTABLES:
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
    labels: Mapping[str, str]
    networks: tuple[str, ...]
    image: str = ""


@dataclass(frozen=True)
class ListenerObservation:
    host: str
    port: int
    ss_output: str
    lsof_output: str


def _child_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    return sanitized_subprocess_environment(dict(extra or {}))


def collect_inventory(executor: CommandExecutor) -> tuple[InventoryItem, ...]:
    result = executor.run((DOCKER, "ps", "-a", "--no-trunc", "--format", "{{json .}}"), env=_child_env())
    items = []
    try:
        for line in filter(str.strip, result.stdout.splitlines()):
            raw = json.loads(line)
            labels = {}
            for entry in filter(None, str(raw.get("Labels", "")).split(",")):
                key, _, value = entry.partition("=")
                labels[key] = value
            items.append(InventoryItem(
                str(raw["ID"]), str(raw["Names"]), labels,
                tuple(filter(None, str(raw.get("Networks", "")).split(","))),
                str(raw.get("Image", "")),
            ))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED) from None
    return tuple(items)


def reject_inventory_collision(items: Sequence[InventoryItem], spec: DockerResourceSpec) -> None:
    for item in items:
        if not isinstance(item.name, str) or not isinstance(item.labels, Mapping):
            raise OrchestrationError(FailureClass.INVENTORY_COLLISION)
        if (item.name == spec.container_name or
                item.labels.get("com.marketingos.test-run-id") == spec.run_id):
            raise OrchestrationError(FailureClass.INVENTORY_COLLISION)


def _inspect_argv(container_id: str) -> tuple[str, ...]:
    if not CONTAINER_ID_PATTERN.fullmatch(container_id):
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
    fields = ("{{json .Id}}", "{{json .Name}}", "{{json .Config.Image}}",
              "{{json .Config.Labels}}", "{{json .State.Running}}",
              "{{json .State.StartedAt}}", "{{json .HostConfig.NetworkMode}}",
              "{{json .NetworkSettings.Ports}}", "{{json .Mounts}}")
    return (DOCKER, "inspect", "--type", "container", "--format", "\n".join(fields), container_id)


def parse_restricted_docker_observation(output: str, spec: DockerResourceSpec) -> dict[str, object]:
    lines = output.splitlines()
    if len(lines) != 9:
        raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED)
    try:
        cid, name, image, labels, running, started, network, ports, mounts = (
            json.loads(line) for line in lines
        )
        binding = ports[f"{spec.internal_port}/tcp"]
        if not isinstance(binding, list) or len(binding) != 1:
            raise ValueError
        sources = [entry["Source"] for entry in mounts]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise OrchestrationError(FailureClass.DOCKER_OBSERVATION_FAILED) from None
    return {"container_id": cid, "container_name": str(name).removeprefix("/"),
            "image_digest": str(image).rsplit("@", 1)[-1], "labels": {key: labels.get(key) for key in spec.labels},
            "running": running, "started_at": started, "networks": [network],
            "published_host": binding[0]["HostIp"],
            "published_port": int(binding[0]["HostPort"]),
            "internal_port": spec.internal_port, "mount_sources": sources}


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
                "mount_sources": [str(spec.temp_dir)] if spec.resource_type == "postgres" else []}
    if any(raw.get(key) != value for key, value in expected.items()):
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)


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


def provisional_rollback(executor: CommandExecutor, spec: DockerResourceSpec,
                         container_id: str) -> bool:
    try:
        raw = collect_docker_observation(executor, spec, container_id)
        validate_provisional_observation(raw, spec, container_id)
    except Exception:
        raise OrchestrationError(FailureClass.ROLLBACK_AUTHORIZATION_FAILED) from None
    try:
        if raw["running"] is True:
            executor.run((DOCKER, "stop", container_id), env=_child_env())
        executor.run((DOCKER, "rm", container_id), env=_child_env())
    except Exception:
        raise OrchestrationError(FailureClass.ROLLBACK_EXECUTION_FAILED) from None
    return True
