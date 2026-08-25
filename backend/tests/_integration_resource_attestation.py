"""Fail-closed validation for disposable integration resource evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping
from urllib.parse import quote

APPROVED_TEMP_ROOT = Path("/tmp/marketingos-integration-resources")
ALEMBIC_TARGET_HEAD = "f0289623eb1e"
RUN_ID_PATTERN = re.compile(r"^r22-[0-9a-f]{16}$")
CONTAINER_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
DOCKER_LABELS = {
    "test": "com.marketingos.test-resource",
    "run": "com.marketingos.test-run-id",
    "type": "com.marketingos.test-resource-type",
}
SENTINEL_KEYS = {
    "resource_run_id", "resource_type", "resource_container_id",
    "resource_pid", "resource_image_digest", "resource_host",
    "resource_port", "resource_temp_dir", "database_name",
    "database_user", "redis_db", "start_time",
}
OBSERVATION_KEYS = SENTINEL_KEYS | {
    "listener_host", "listener_port", "docker_labels", "container_name",
    "running", "internal_port", "mount_sources", "mount_details",
    "host_tmpfs", "declared_volumes", "networks",
}


class ResourceAttestationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResourceAttestation:
    resource_run_id: str
    resource_type: str
    resource_container_id: str | None
    resource_pid: int | None
    resource_image_digest: str
    resource_host: str
    resource_port: int
    resource_temp_dir: Path
    database_name: str | None
    database_user: str | None
    redis_db: int | None
    start_time: str


def _fail(message: str) -> None:
    raise ResourceAttestationError(message)


def lifecycle_operator_identity() -> tuple[int, int]:
    """Return the only trusted ownership identity for lifecycle metadata."""
    return os.geteuid(), os.getegid()


def _validate_metadata_stat(metadata: os.stat_result, *, expected_uid: int,
                            expected_gid: int) -> None:
    if not stat.S_ISREG(metadata.st_mode):
        _fail("attestation must be a regular file")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        _fail("attestation file must be mode 0600")
    if metadata.st_uid != expected_uid:
        _fail("attestation owner UID differs from lifecycle operator")
    if metadata.st_gid != expected_gid:
        _fail("attestation owner GID differs from lifecycle operator")


def validate_operator_owned_metadata(path: Path) -> None:
    """Fail closed unless path is operator-owned regular mode-0600 metadata."""
    expected_uid, expected_gid = lifecycle_operator_identity()
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ResourceAttestationError("attestation path unavailable") from exc
    _validate_metadata_stat(metadata, expected_uid=expected_uid,
                            expected_gid=expected_gid)


def _under(path: Path, root: Path) -> Path:
    if not path.is_absolute() or not root.is_absolute():
        _fail("attestation paths must be absolute")
    if path.is_symlink() or root.is_symlink():
        _fail("attestation paths must not be symlinks")
    try:
        canonical_root = root.resolve(strict=True)
        canonical = path.resolve(strict=True)
    except OSError as exc:
        raise ResourceAttestationError("attestation path unavailable") from exc
    if canonical == canonical_root or canonical_root not in canonical.parents:
        _fail("attestation path outside approved temporary root")
    try:
        relative = path.relative_to(root)
    except ValueError:
        _fail("attestation path must be lexically below approved root")
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            _fail("attestation path contains symlink traversal")
    return canonical


def _read(path: Path, keys: set[str]) -> dict[str, Any]:
    validate_operator_owned_metadata(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ResourceAttestationError("attestation path unavailable") from exc
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            expected_uid, expected_gid = lifecycle_operator_identity()
            _validate_metadata_stat(
                os.fstat(handle.fileno()), expected_uid=expected_uid,
                expected_gid=expected_gid,
            )
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResourceAttestationError("attestation JSON invalid") from exc
    if not isinstance(value, dict) or set(value) != keys:
        _fail("attestation JSON schema mismatch")
    return value


def _validated(
    data: Mapping[str, Any], *, expected_run_id: str,
    expected_type: str, approved_root: Path,
) -> ResourceAttestation:
    run_id, kind = data["resource_run_id"], data["resource_type"]
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.fullmatch(run_id):
        _fail("run-id format invalid")
    if run_id != expected_run_id or kind != expected_type or kind not in {"postgres", "redis"}:
        _fail("run-id or resource-type mismatch")
    cid, pid = data["resource_container_id"], data["resource_pid"]
    if (cid is None) == (pid is None):
        _fail("exactly one container ID or PID required")
    if cid is not None and (not isinstance(cid, str) or not CONTAINER_ID_PATTERN.fullmatch(cid)):
        _fail("container ID invalid")
    if pid is not None and (not isinstance(pid, int) or isinstance(pid, bool) or pid <= 1):
        _fail("PID invalid")
    digest = data["resource_image_digest"]
    if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        _fail("immutable image/process digest invalid")
    if data["resource_host"] != "127.0.0.1":
        _fail("resource host must be explicit loopback")
    port = data["resource_port"]
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535 or port in {5432, 6379}:
        _fail("resource port invalid or prohibited")
    temp_dir = _under(Path(data["resource_temp_dir"]), approved_root)
    run_dir = approved_root.resolve(strict=True) / run_id
    if stat.S_IMODE(run_dir.stat().st_mode) != 0o700:
        _fail("run directory must be mode 0700")
    if stat.S_IMODE(temp_dir.stat().st_mode) != 0o700:
        _fail("resource directory must be mode 0700")
    if temp_dir != approved_root.resolve(strict=True) / run_id / kind:
        _fail("resource directory identity mismatch")
    safe_id = run_id.removeprefix("r22-")
    db, user, redis_db = data["database_name"], data["database_user"], data["redis_db"]
    if kind == "postgres":
        if db != f"marketingos_test_r22_{safe_id}" or user != f"marketingos_test_{safe_id}" or redis_db is not None:
            _fail("PostgreSQL identity is not run-scoped")
    elif db is not None or user is not None or not isinstance(redis_db, int) or isinstance(redis_db, bool) or not 1 <= redis_db <= 15:
        _fail("Redis identity invalid")
    started = data["start_time"]
    if not isinstance(started, str) or not started.endswith("Z"):
        _fail("start time must be RFC3339 UTC")
    try:
        datetime.fromisoformat(started[:-1] + "+00:00")
    except ValueError as exc:
        raise ResourceAttestationError("start time invalid") from exc
    return ResourceAttestation(run_id, kind, cid, pid, digest, "127.0.0.1", port, temp_dir, db, user, redis_db, started)


def load_sentinel(path: str | os.PathLike[str], *, expected_run_id: str,
                  expected_type: str, approved_root: Path = APPROVED_TEMP_ROOT) -> ResourceAttestation:
    sentinel = _under(Path(path), approved_root)
    if sentinel.parent.parent.name != expected_run_id:
        _fail("sentinel path run-id mismatch")
    return _validated(_read(sentinel, SENTINEL_KEYS), expected_run_id=expected_run_id,
                      expected_type=expected_type, approved_root=approved_root)


def validate_runtime_observation(attestation: ResourceAttestation,
                                 path: str | os.PathLike[str], *,
                                 approved_root: Path = APPROVED_TEMP_ROOT) -> None:
    data = _read(_under(Path(path), approved_root), OBSERVATION_KEYS)
    observed = _validated(data, expected_run_id=attestation.resource_run_id,
                          expected_type=attestation.resource_type, approved_root=approved_root)
    if observed != attestation:
        _fail("runtime identity differs from sentinel")
    if data["listener_host"] != "127.0.0.1" or data["listener_port"] != attestation.resource_port:
        _fail("listener identity mismatch")
    expected_name = f"marketingos-{attestation.resource_run_id}-{attestation.resource_type}"
    if data["container_name"] != expected_name or data["running"] is not True:
        _fail("container name/state mismatch")
    expected_internal_port = 5432 if attestation.resource_type == "postgres" else 6379
    if data["internal_port"] != expected_internal_port:
        _fail("container internal port mismatch")
    mounts = data["mount_sources"]
    mount_details = data["mount_details"]
    host_tmpfs = data["host_tmpfs"]
    declared_volumes = data["declared_volumes"]
    if (not isinstance(declared_volumes, list) or
            any(not isinstance(value, str) for value in declared_volumes)):
        _fail("image-declared volume metadata invalid")
    if attestation.resource_type == "postgres":
        source = str(attestation.resource_temp_dir / "data")
        if mounts != [source] or mount_details != [{
            "type": "bind", "source": source,
            "destination": "/var/lib/postgresql/data", "rw": True,
        }] or host_tmpfs is not None:
            _fail("PostgreSQL mount identity mismatch")
    elif (mounts != [] or mount_details != [] or host_tmpfs != {
            "destination": "/data", "rw": True,
            "size_bytes": 67108864, "mode": "0700",
    }):
        _fail("Redis tmpfs storage identity mismatch")
    if data["networks"] != ["bridge"]:
        _fail("Docker network identity mismatch")
    labels = data["docker_labels"]
    if attestation.resource_container_id is not None:
        expected = {DOCKER_LABELS["test"]: "true", DOCKER_LABELS["run"]: attestation.resource_run_id,
                    DOCKER_LABELS["type"]: attestation.resource_type}
        if labels != expected:
            _fail("Docker labels mismatch")
    elif labels != {}:
        _fail("native process must not claim Docker labels")


def authorize_destructive_cleanup(attestation: ResourceAttestation,
                                  observation_path: str | os.PathLike[str], *,
                                  approved_root: Path = APPROVED_TEMP_ROOT) -> None:
    validate_runtime_observation(attestation, observation_path, approved_root=approved_root)


def reconstruct_database_url(attestation: ResourceAttestation, password: str) -> str:
    if attestation.resource_type != "postgres" or not password:
        _fail("PostgreSQL attestation and runtime password required")
    return (f"postgresql+asyncpg://{quote(attestation.database_user or '', safe='')}:"
            f"{quote(password, safe='')}@127.0.0.1:{attestation.resource_port}/"
            f"{quote(attestation.database_name or '', safe='')}")


def reconstruct_redis_url(attestation: ResourceAttestation) -> str:
    if attestation.resource_type != "redis":
        _fail("Redis attestation required")
    return f"redis://127.0.0.1:{attestation.resource_port}/{attestation.redis_db}"


def validate_candidate_port(port: int, *, ss_listener_output: str,
                            lsof_listener_output: str) -> None:
    """Validate trusted-tool pre-start results without killing a listener."""
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        _fail("candidate port must be a high TCP port")
    if port in {5432, 6379}:
        _fail("default service port is prohibited")
    if ss_listener_output.strip() or lsof_listener_output.strip():
        _fail("candidate port already has a listener")


def validate_migration_gate(attestation: ResourceAttestation,
                            observation_path: str | os.PathLike[str], *, requested_head: str,
                            approved_root: Path = APPROVED_TEMP_ROOT,
                            environment: Mapping[str, str] | None = None) -> None:
    if attestation.resource_type != "postgres" or requested_head != ALEMBIC_TARGET_HEAD:
        _fail("migration target gate mismatch")
    required_environment = {
        "ENVIRONMENT": "test",
        "MARKETINGOS_TEST_MODE": "integration",
        "MARKETINGOS_TEST_RESOURCE_SCOPE": "disposable",
    }
    source_environment = os.environ if environment is None else environment
    if any(source_environment.get(name) != value for name, value in required_environment.items()):
        _fail("migration environment gate mismatch")
    validate_runtime_observation(attestation, observation_path, approved_root=approved_root)


def safe_diagnostic(attestation: ResourceAttestation, test_file: str) -> dict[str, object]:
    identity = attestation.resource_container_id or str(attestation.resource_pid)
    return {"run_id": attestation.resource_run_id, "resource_type": attestation.resource_type,
            "resource_identity": identity[:12], "image_digest": attestation.resource_image_digest,
            "host": attestation.resource_host, "port": attestation.resource_port,
            "database_name": attestation.database_name, "redis_db": attestation.redis_db,
            "temp_dir": str(attestation.resource_temp_dir), "test_file": test_file, "guard": "PASS"}
