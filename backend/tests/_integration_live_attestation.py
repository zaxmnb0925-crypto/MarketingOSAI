"""Daemon-derived attestation used by real migration/test/teardown paths."""
from __future__ import annotations

from pathlib import Path

from _integration_execute_orchestration import (
    CommandExecutor, FailureClass, OrchestrationError,
    collect_docker_observation, observe_listener, require_loopback_listener,
)
from _integration_resource_attestation import APPROVED_TEMP_ROOT, load_sentinel
from _integration_resource_lifecycle import (
    build_docker_spec, normalize_docker_observation, sentinel_payload,
)


def attest_live_resource(*, sentinel_path: str | Path, run_id: str,
                         resource_type: str, image: str,
                         executor: CommandExecutor,
                         approved_root: Path = APPROVED_TEMP_ROOT):
    attested = load_sentinel(sentinel_path, expected_run_id=run_id,
                             expected_type=resource_type, approved_root=approved_root)
    if not attested.resource_container_id:
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
    spec = build_docker_spec(run_id=run_id, resource_type=resource_type, image=image,
                             port=attested.resource_port, redis_db=attested.redis_db or 15,
                             approved_root=approved_root)
    observed = normalize_docker_observation(
        collect_docker_observation(executor, spec, attested.resource_container_id), spec)
    require_loopback_listener(observe_listener(executor, spec.port))
    expected = dict(attested.__dict__)
    expected["resource_temp_dir"] = str(attested.resource_temp_dir)
    if sentinel_payload(observed) != sentinel_payload(expected):
        raise OrchestrationError(FailureClass.RESOURCE_IDENTITY_MISMATCH)
    return attested
