from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Iterable
from uuid import UUID

from app.models.ai_quality_policy_governance import AIQualityPolicyGovernanceCaseStatus
from app.models.ai_quality_policy_remediation import AIQualityPolicyRemediationStatus


class QualityPolicyGovernanceError(RuntimeError):
    pass


class GovernanceConcurrencyConflict(QualityPolicyGovernanceError):
    pass


class GovernanceClosureDecision(str, Enum):
    close = "close"
    reject = "reject"
    void = "void"


@dataclass(frozen=True)
class GovernanceEvidenceInput:
    evidence_type: str
    source_table: str
    source_record_id: UUID
    source_state: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class GovernanceEvidenceSnapshot:
    sequence: int
    evidence_type: str
    source_table: str
    source_record_id: UUID
    source_state: str
    payload_sha256: str
    payload: dict[str, Any]


_PROHIBITED_KEYS = {
    "password", "secret", "token", "api_key", "authorization",
    "postgres_password", "database_url", "pgdata",
}
_PROHIBITED_PATH_MARKERS = ("postgres-docker.env", "postgres-password", "/pgdata", "/data/base/")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")


def _validate_non_secret(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _PROHIBITED_KEYS or normalized.endswith("_secret") or normalized.endswith("_token") or normalized.endswith("_password"):
                raise QualityPolicyGovernanceError(f"secret-bearing evidence field prohibited: {path}.{key}")
            _validate_non_secret(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_non_secret(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _PROHIBITED_PATH_MARKERS):
            raise QualityPolicyGovernanceError(f"secret or PGDATA path prohibited: {path}")


def build_governance_evidence_manifest(items: Iterable[GovernanceEvidenceInput]) -> tuple[list[GovernanceEvidenceSnapshot], str]:
    values = list(items)
    if not 1 <= len(values) <= 100:
        raise QualityPolicyGovernanceError("governance evidence item count must be between 1 and 100")
    ordered = sorted(values, key=lambda item: (item.evidence_type, item.source_table, str(item.source_record_id)))
    seen: set[tuple[str, UUID]] = set()
    snapshots: list[GovernanceEvidenceSnapshot] = []
    for sequence, item in enumerate(ordered, start=1):
        identity = (item.source_table, item.source_record_id)
        if identity in seen:
            raise QualityPolicyGovernanceError("duplicate governance evidence source")
        seen.add(identity)
        _validate_non_secret(item.payload)
        payload_sha = hashlib.sha256(_canonical_json(item.payload)).hexdigest()
        snapshots.append(GovernanceEvidenceSnapshot(sequence, item.evidence_type, item.source_table, item.source_record_id, item.source_state, payload_sha, item.payload))
    manifest = [{"sequence": item.sequence, "evidence_type": item.evidence_type, "source_table": item.source_table, "source_record_id": str(item.source_record_id), "source_state": item.source_state, "payload_sha256": item.payload_sha256} for item in snapshots]
    return snapshots, hashlib.sha256(_canonical_json(manifest)).hexdigest()


def validate_governance_case_opening(*, remediation_status: AIQualityPolicyRemediationStatus, remediation_workspace_id: UUID, remediation_brand_id: UUID, workspace_id: UUID, brand_id: UUID, expected_policy_version: int, remediation_policy_version: int) -> None:
    if remediation_status not in {AIQualityPolicyRemediationStatus.recovered, AIQualityPolicyRemediationStatus.failed}:
        raise QualityPolicyGovernanceError("only recovered or failed remediation may enter governance closure")
    if remediation_workspace_id != workspace_id or remediation_brand_id != brand_id:
        raise QualityPolicyGovernanceError("cross-scope governance case prohibited")
    if expected_policy_version != remediation_policy_version:
        raise GovernanceConcurrencyConflict("remediation policy version changed before case opening")


def plan_governance_case_closure(*, current_status: AIQualityPolicyGovernanceCaseStatus, expected_manifest_sha256: str, current_manifest_sha256: str, decision: GovernanceClosureDecision, human_confirms_closure: bool, reason: str) -> AIQualityPolicyGovernanceCaseStatus:
    if current_status != AIQualityPolicyGovernanceCaseStatus.open:
        raise QualityPolicyGovernanceError("governance case is already terminal")
    if expected_manifest_sha256 != current_manifest_sha256:
        raise GovernanceConcurrencyConflict("evidence manifest changed before closure")
    if not human_confirms_closure:
        raise QualityPolicyGovernanceError("explicit human closure confirmation required")
    if not reason.strip():
        raise QualityPolicyGovernanceError("closure reason required")
    return {
        GovernanceClosureDecision.close: AIQualityPolicyGovernanceCaseStatus.closed,
        GovernanceClosureDecision.reject: AIQualityPolicyGovernanceCaseStatus.rejected,
        GovernanceClosureDecision.void: AIQualityPolicyGovernanceCaseStatus.voided,
    }[decision]
