"""Pure lifecycle planning for disposable integration resources.

No function in this module invokes Docker, a database, Redis, or Alembic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from typing import Any, Mapping

from _integration_docker_command import docker_command
from _integration_resource_attestation import (
    ALEMBIC_TARGET_HEAD,
    APPROVED_TEMP_ROOT,
    CONTAINER_ID_PATTERN,
    DIGEST_PATTERN,
    DOCKER_LABELS,
    RUN_ID_PATTERN,
    ResourceAttestation,
    ResourceAttestationError,
    authorize_destructive_cleanup,
    load_sentinel,
    reconstruct_database_url,
    validate_candidate_port,
    validate_migration_gate,
    validate_runtime_observation,
)

IMAGE_PATTERN = re.compile(
    r"^[a-z0-9]+(?:[._/-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
    r"@sha256:[0-9a-f]{64}$"
)
REDIS_TMPFS_DESTINATION = "/data"
REDIS_TMPFS_SIZE_BYTES = 64 * 1024 * 1024
REDIS_TMPFS_MODE = 0o700
REDIS_TMPFS_OPTION = (
    f"{REDIS_TMPFS_DESTINATION}:rw,size={REDIS_TMPFS_SIZE_BYTES},mode={REDIS_TMPFS_MODE:04o}"
)
REDIS_TMPFS_ATTESTATION = {
    "destination": REDIS_TMPFS_DESTINATION, "rw": True,
    "size_bytes": REDIS_TMPFS_SIZE_BYTES, "mode": "0700",
}


def normalize_redis_tmpfs_configuration(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {REDIS_TMPFS_DESTINATION}:
        raise ResourceAttestationError("Redis HostConfig.Tmpfs identity mismatch")
    options = value[REDIS_TMPFS_DESTINATION]
    if not isinstance(options, str):
        raise ResourceAttestationError("Redis HostConfig.Tmpfs options invalid")
    tokens = options.split(",")
    if len(tokens) != 3 or any(not token for token in tokens) or len(set(tokens)) != 3:
        raise ResourceAttestationError("Redis HostConfig.Tmpfs options invalid")
    if set(tokens) != {"rw", "size=67108864", "mode=0700"}:
        raise ResourceAttestationError("Redis HostConfig.Tmpfs options mismatch")
    return dict(REDIS_TMPFS_ATTESTATION)

ORCHESTRATION_ORDER = (
    "provision", "observe", "attest", "migrate-postgres",
    "single-integration-file", "verify", "exact-teardown",
)


@dataclass(frozen=True)
class DockerResourceSpec:
    run_id: str
    resource_type: str
    image: str
    image_digest: str
    container_name: str
    host: str
    port: int
    internal_port: int
    temp_dir: Path
    pgdata_dir: Path | None
    database_name: str | None
    database_user: str | None
    redis_db: int | None
    labels: Mapping[str, str]
    argv: tuple[str, ...]
    required_secret_environment: tuple[str, ...]

    def sanitized_plan(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "resource_type": self.resource_type,
            "image": self.image,
            "image_digest": self.image_digest,
            "container_name": self.container_name,
            "host": self.host,
            "port": self.port,
            "internal_port": self.internal_port,
            "temp_dir": str(self.temp_dir),
            "database_name": self.database_name,
            "pgdata_dir": str(self.pgdata_dir) if self.pgdata_dir else None,
            "database_user": self.database_user,
            "redis_db": self.redis_db,
            "labels": dict(self.labels),
            "required_secret_environment": list(self.required_secret_environment),
        }


def generate_run_id() -> str:
    return "r22-" + secrets.token_hex(8)


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ResourceAttestationError("run-id format invalid")
    return run_id


def validate_image_reference(image: str) -> str:
    if not IMAGE_PATTERN.fullmatch(image):
        raise ResourceAttestationError("image must use repository@sha256:<64 lowercase hex>")
    return image.rsplit("@", 1)[1]


def container_name(run_id: str, resource_type: str) -> str:
    validate_run_id(run_id)
    if resource_type not in {"postgres", "redis"}:
        raise ResourceAttestationError("resource type invalid")
    return f"marketingos-{run_id}-{resource_type}"


def resource_temp_dir(run_id: str, resource_type: str,
                      approved_root: Path = APPROVED_TEMP_ROOT) -> Path:
    validate_run_id(run_id)
    if resource_type not in {"postgres", "redis"}:
        raise ResourceAttestationError("resource type invalid")
    if not approved_root.is_absolute() or approved_root == Path("/tmp"):
        raise ResourceAttestationError("approved root invalid")
    if Path("/tmp") not in approved_root.parents:
        raise ResourceAttestationError("approved root must be strictly below /tmp")
    if approved_root.exists() and approved_root.is_symlink():
        raise ResourceAttestationError("approved root must not be a symlink")
    current = Path("/tmp")
    for component in approved_root.relative_to(Path("/tmp")).parts:
        current = current / component
        if current.exists() and current.is_symlink():
            raise ResourceAttestationError("approved root contains symlink traversal")
    if approved_root.exists() and Path("/tmp").resolve(strict=True) not in approved_root.resolve(strict=True).parents:
        raise ResourceAttestationError("approved root canonical path escaped /tmp")
    candidate = approved_root / run_id / resource_type
    repository = Path(__file__).resolve().parents[2]
    if repository == candidate or repository in candidate.parents:
        raise ResourceAttestationError("resource directory must be outside repository")
    return candidate


def create_resource_directories(run_id: str, resource_type: str,
                                approved_root: Path = APPROVED_TEMP_ROOT) -> Path:
    target = resource_temp_dir(run_id, resource_type, approved_root)
    if approved_root.is_symlink() or target.is_symlink():
        raise ResourceAttestationError("resource path must not be a symlink")
    approved_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    approved_root.chmod(0o700)
    run_dir = approved_root / run_id
    run_dir.mkdir(mode=0o700, exist_ok=True)
    run_dir.chmod(0o700)
    target.mkdir(mode=0o700, exist_ok=False)
    if resource_type == "postgres":
        (target / "data").mkdir(mode=0o700)
    return target


def postgres_data_dir(run_id: str, *,
                      approved_root: Path = APPROVED_TEMP_ROOT) -> Path:
    """Return the only path permitted as the PostgreSQL PGDATA bind source."""
    return resource_temp_dir(run_id, "postgres", approved_root) / "data"


def require_empty_postgres_data_dir(spec: DockerResourceSpec) -> Path:
    """Fail closed unless the exact, non-symlink PGDATA directory is empty."""
    if spec.resource_type != "postgres" or spec.pgdata_dir is None:
        raise ResourceAttestationError("PostgreSQL data directory unavailable")
    expected = spec.temp_dir / "data"
    if spec.pgdata_dir != expected:
        raise ResourceAttestationError("PostgreSQL data path identity mismatch")
    if spec.temp_dir.is_symlink() or spec.pgdata_dir.is_symlink():
        raise ResourceAttestationError("PostgreSQL data path must not use symlinks")
    try:
        root = spec.temp_dir.resolve(strict=True)
        data = spec.pgdata_dir.resolve(strict=True)
    except OSError as exc:
        raise ResourceAttestationError("PostgreSQL data path unavailable") from exc
    if data != root / "data" or root not in data.parents or not data.is_dir():
        raise ResourceAttestationError("PostgreSQL data path escaped resource root")
    if next(data.iterdir(), None) is not None:
        raise ResourceAttestationError("PGDATA_NOT_EMPTY")
    return data


def build_docker_spec(*, run_id: str, resource_type: str, image: str,
                      port: int, redis_db: int = 15,
                      approved_root: Path = APPROVED_TEMP_ROOT) -> DockerResourceSpec:
    validate_run_id(run_id)
    digest = validate_image_reference(image)
    validate_candidate_port(port, ss_listener_output="", lsof_listener_output="")
    name = container_name(run_id, resource_type)
    temp_dir = resource_temp_dir(run_id, resource_type, approved_root)
    pgdata_dir = temp_dir / "data" if resource_type == "postgres" else None
    safe_id = run_id.removeprefix("r22-")
    labels = {
        DOCKER_LABELS["test"]: "true",
        DOCKER_LABELS["run"]: run_id,
        DOCKER_LABELS["type"]: resource_type,
    }
    prefix = list(docker_command("create", "--name", name, "--network", "bridge"))
    for key, value in labels.items():
        prefix += ["--label", f"{key}={value}"]
    if resource_type == "postgres":
        database_name = f"marketingos_test_r22_{safe_id}"
        database_user = f"marketingos_test_{safe_id}"
        internal_port = 5432
        prefix += [
            "--publish", f"127.0.0.1:{port}:5432",
            "--mount", f"type=bind,src={pgdata_dir},dst=/var/lib/postgresql/data",
            "--env", f"POSTGRES_DB={database_name}",
            "--env", f"POSTGRES_USER={database_user}",
            "--env", "POSTGRES_PASSWORD",
            image,
        ]
        required = ("POSTGRES_PASSWORD",)
        redis_value = None
    elif resource_type == "redis":
        if not isinstance(redis_db, int) or isinstance(redis_db, bool) or not 1 <= redis_db <= 15:
            raise ResourceAttestationError("Redis DB must be non-zero")
        database_name = database_user = None
        internal_port = 6379
        prefix += [
            "--publish", f"127.0.0.1:{port}:6379",
            "--tmpfs", REDIS_TMPFS_OPTION,
            image, "redis-server", "--save", "", "--appendonly", "no",
        ]
        required = ()
        redis_value = redis_db
    else:
        raise ResourceAttestationError("resource type invalid")
    prohibited = {"--privileged", "--pid=host", "--network=host"}
    if prohibited.intersection(prefix):
        raise ResourceAttestationError("prohibited Docker option")
    return DockerResourceSpec(
        run_id, resource_type, image, digest, name, "127.0.0.1", port,
        internal_port, temp_dir, pgdata_dir, database_name, database_user, redis_value,
        labels, tuple(prefix), required,
    )


def normalize_docker_observation(raw: Mapping[str, Any],
                                 spec: DockerResourceSpec) -> dict[str, Any]:
    required = {
        "container_id", "image_digest", "labels", "container_name", "running",
        "published_host", "published_port", "internal_port", "started_at",
        "mount_sources", "mount_details", "host_tmpfs", "declared_volumes",
        "networks",
    }
    if set(raw) != required:
        raise ResourceAttestationError("Docker observation schema mismatch")
    if raw["container_name"] != spec.container_name or raw["running"] is not True:
        raise ResourceAttestationError("container name/state mismatch")
    if not isinstance(raw["container_id"], str) or not CONTAINER_ID_PATTERN.fullmatch(raw["container_id"]):
        raise ResourceAttestationError("container ID invalid")
    if raw["image_digest"] != spec.image_digest or raw["labels"] != dict(spec.labels):
        raise ResourceAttestationError("container digest/labels mismatch")
    if raw["published_host"] != "127.0.0.1" or raw["published_port"] != spec.port:
        raise ResourceAttestationError("published listener mismatch")
    if raw["internal_port"] != spec.internal_port:
        raise ResourceAttestationError("internal port mismatch")
    mounts = raw["mount_sources"]
    mount_details = raw["mount_details"]
    host_tmpfs = raw["host_tmpfs"]
    declared_volumes = raw["declared_volumes"]
    if declared_volumes is not None and (
            not isinstance(declared_volumes, Mapping) or
            any(not isinstance(key, str) or value not in ({}, None)
                for key, value in declared_volumes.items())):
        raise ResourceAttestationError("image-declared volume metadata invalid")
    declared_volume_destinations = sorted((declared_volumes or {}).keys())
    expected_mount = str(spec.pgdata_dir) if spec.resource_type == "postgres" else None
    if not isinstance(mounts, list) or any(
        not isinstance(value, str) or Path(value) != spec.pgdata_dir
        for value in mounts
    ):
        raise ResourceAttestationError("unexpected mount identity")
    if spec.resource_type == "postgres":
        if mounts != [expected_mount] or mount_details != [{
            "type": "bind", "source": expected_mount,
            "destination": "/var/lib/postgresql/data", "rw": True,
        }]:
            raise ResourceAttestationError("PostgreSQL data mount mismatch")
        if host_tmpfs not in (None, {}):
            raise ResourceAttestationError("PostgreSQL HostConfig.Tmpfs must be empty")
        normalized_tmpfs = None
    else:
        if mounts != [] or mount_details != []:
            raise ResourceAttestationError("Redis persistent Docker mounts prohibited")
        normalized_tmpfs = normalize_redis_tmpfs_configuration(host_tmpfs)
    if raw["networks"] != ["bridge"]:
        raise ResourceAttestationError("unexpected Docker network identity")
    try:
        datetime.fromisoformat(str(raw["started_at"]).removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ResourceAttestationError("Docker start time invalid") from exc
    return {
        "resource_run_id": spec.run_id,
        "resource_type": spec.resource_type,
        "resource_container_id": raw["container_id"],
        "resource_pid": None,
        "resource_image_digest": raw["image_digest"],
        "resource_host": spec.host,
        "resource_port": spec.port,
        "resource_temp_dir": str(spec.temp_dir),
        "database_name": spec.database_name,
        "database_user": spec.database_user,
        "redis_db": spec.redis_db,
        "start_time": raw["started_at"],
        "listener_host": raw["published_host"],
        "listener_port": raw["published_port"],
        "docker_labels": raw["labels"],
        "container_name": raw["container_name"],
        "running": raw["running"],
        "internal_port": raw["internal_port"],
        "mount_sources": mounts,
        "mount_details": mount_details,
        "host_tmpfs": normalized_tmpfs,
        "declared_volumes": declared_volume_destinations,
        "networks": raw["networks"],
    }


def sentinel_payload(observation: Mapping[str, Any]) -> dict[str, Any]:
    from _integration_resource_attestation import SENTINEL_KEYS
    if not SENTINEL_KEYS.issubset(observation):
        raise ResourceAttestationError("observation cannot produce sentinel")
    return {key: observation[key] for key in SENTINEL_KEYS}


def write_secure_json(path: Path, payload: Mapping[str, Any], *,
                      approved_root: Path = APPROVED_TEMP_ROOT) -> None:
    forbidden_fragments = ("password", "secret", "token", "database_url", "redis_url", "fernet")
    if any(fragment in key.lower() for key in payload for fragment in forbidden_fragments):
        raise ResourceAttestationError("secret field prohibited in evidence")
    serialized = json.dumps(dict(payload), sort_keys=True)
    if any("://" in str(value) and "@" in str(value) for value in payload.values()):
        raise ResourceAttestationError("credential-bearing URL prohibited in evidence")
    expected_parent = resource_temp_dir(
        str(payload["resource_run_id"]), str(payload["resource_type"]), approved_root
    )
    if path.parent.resolve(strict=True) != expected_parent.resolve(strict=True):
        raise ResourceAttestationError("evidence path identity mismatch")
    if path.exists() or path.is_symlink():
        raise ResourceAttestationError("evidence file already exists")
    temporary = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    pgdata = expected_parent / "data"
    if path == pgdata or pgdata in path.parents:
        raise ResourceAttestationError("evidence must remain outside PGDATA")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.is_symlink() or stat.S_IMODE(temporary.stat().st_mode) != 0o600:
            raise ResourceAttestationError("temporary evidence mode invalid")
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if path.is_symlink() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ResourceAttestationError("evidence transaction verification failed")
    except Exception:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def authorize_migration(*, sentinel_path: Path, observation_path: Path,
                        run_id: str, runtime_password: str,
                        approved_root: Path = APPROVED_TEMP_ROOT) -> tuple[str, ...]:
    attested = load_sentinel(sentinel_path, expected_run_id=run_id,
                             expected_type="postgres", approved_root=approved_root)
    validate_migration_gate(attested, observation_path,
                            requested_head=ALEMBIC_TARGET_HEAD,
                            approved_root=approved_root)
    reconstruct_database_url(attested, runtime_password)
    return (sys.executable, "-m", "alembic", "upgrade", ALEMBIC_TARGET_HEAD)


def authorize_teardown(*, sentinel_path: Path, observation_path: Path,
                       run_id: str, resource_type: str,
                       approved_root: Path = APPROVED_TEMP_ROOT) -> tuple[tuple[str, ...], ...]:
    attested = load_sentinel(sentinel_path, expected_run_id=run_id,
                             expected_type=resource_type, approved_root=approved_root)
    authorize_destructive_cleanup(attested, observation_path, approved_root=approved_root)
    validate_cleanup_path(attested.resource_temp_dir, run_id=run_id,
                          resource_type=resource_type, approved_root=approved_root)
    if attested.resource_container_id is None:
        raise ResourceAttestationError("Docker teardown requires exact container ID")
    exact = attested.resource_container_id
    return (docker_command("stop", exact), docker_command("rm", exact))


def validate_cleanup_path(path: Path, *, run_id: str, resource_type: str,
                          approved_root: Path = APPROVED_TEMP_ROOT) -> Path:
    expected = resource_temp_dir(run_id, resource_type, approved_root)
    if path.is_symlink() or approved_root.is_symlink():
        raise ResourceAttestationError("cleanup path must not use symlinks")
    try:
        canonical = path.resolve(strict=True)
        canonical_root = approved_root.resolve(strict=True)
    except OSError as exc:
        raise ResourceAttestationError("cleanup path unavailable") from exc
    if canonical != expected.resolve(strict=True):
        raise ResourceAttestationError("cleanup path identity mismatch")
    if canonical in {Path("/"), Path("/tmp"), Path("/home"), Path("/opt"), canonical_root}:
        raise ResourceAttestationError("cleanup path is too broad")
    repository = Path(__file__).resolve().parents[2]
    if canonical == repository or repository in canonical.parents:
        raise ResourceAttestationError("cleanup path must be outside repository")
    return canonical


def sanitized_subprocess_environment(extra: Mapping[str, str]) -> dict[str, str]:
    permitted = {
        "POSTGRES_PASSWORD", "DATABASE_URL", "REDIS_URL", "ENVIRONMENT",
        "MARKETINGOS_TEST_MODE", "MARKETINGOS_TEST_RESOURCE_SCOPE", "TEST_RUN_ID",
        "SECRET_KEY", "OPENAI_API_KEY", "OAUTH_TOKEN_ENCRYPTION_KEY",
        "API_DOCS_ENABLED", "REAL_PUBLISH_ENABLED",
        "META_PUBLISH_TRANSPORT_ENABLED", "META_PUBLISH_CANARY_MODE_ENABLED",
    }
    unexpected = set(extra) - permitted
    if unexpected:
        raise ResourceAttestationError("subprocess environment key is not allowlisted")
    result = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    result.update(extra)
    return result
