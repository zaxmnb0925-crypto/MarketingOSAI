from uuid import UUID

import pytest

from app.models.ai_quality_policy_governance import AIQualityPolicyGovernanceCaseStatus
from app.models.ai_quality_policy_remediation import AIQualityPolicyRemediationStatus
from app.services.ai_quality_policy_governance import (
    GovernanceClosureDecision,
    GovernanceConcurrencyConflict,
    GovernanceEvidenceInput,
    QualityPolicyGovernanceError,
    build_governance_evidence_manifest,
    plan_governance_case_closure,
    validate_governance_case_opening,
)


WORKSPACE = UUID("10000000-0000-0000-0000-000000000001")
BRAND = UUID("20000000-0000-0000-0000-000000000001")


def evidence(record: str, payload: dict | None = None) -> GovernanceEvidenceInput:
    return GovernanceEvidenceInput(
        evidence_type="remediation",
        source_table="ai_quality_policy_remediations",
        source_record_id=UUID(record),
        source_state="recovered",
        payload=payload or {"status": "recovered", "policy_version": 2},
    )


def test_manifest_is_deterministic_and_sequence_is_canonical() -> None:
    first = evidence("30000000-0000-0000-0000-000000000001")
    second = GovernanceEvidenceInput(
        evidence_type="activation",
        source_table="ai_quality_policy_activations",
        source_record_id=UUID("40000000-0000-0000-0000-000000000001"),
        source_state="active",
        payload={"policy_version": 1, "status": "active"},
    )
    snapshots_a, digest_a = build_governance_evidence_manifest([first, second])
    snapshots_b, digest_b = build_governance_evidence_manifest([second, first])
    assert digest_a == digest_b
    assert [item.sequence for item in snapshots_a] == [1, 2]
    assert [item.payload_sha256 for item in snapshots_a] == [item.payload_sha256 for item in snapshots_b]
    assert len(digest_a) == 64


def test_manifest_rejects_secrets_pgdata_and_duplicate_sources() -> None:
    with pytest.raises(QualityPolicyGovernanceError, match="secret-bearing"):
        build_governance_evidence_manifest([evidence("30000000-0000-0000-0000-000000000001", {"api_key": "forbidden"})])
    with pytest.raises(QualityPolicyGovernanceError, match="PGDATA"):
        build_governance_evidence_manifest([evidence("30000000-0000-0000-0000-000000000001", {"path": "/tmp/run/pgdata"})])
    duplicate = evidence("30000000-0000-0000-0000-000000000001")
    with pytest.raises(QualityPolicyGovernanceError, match="duplicate"):
        build_governance_evidence_manifest([duplicate, duplicate])


def test_case_opening_requires_terminal_remediation_and_exact_scope() -> None:
    validate_governance_case_opening(
        remediation_status=AIQualityPolicyRemediationStatus.recovered,
        remediation_workspace_id=WORKSPACE,
        remediation_brand_id=BRAND,
        workspace_id=WORKSPACE,
        brand_id=BRAND,
        expected_policy_version=2,
        remediation_policy_version=2,
    )
    with pytest.raises(QualityPolicyGovernanceError, match="recovered or failed"):
        validate_governance_case_opening(
            remediation_status=AIQualityPolicyRemediationStatus.observation,
            remediation_workspace_id=WORKSPACE,
            remediation_brand_id=BRAND,
            workspace_id=WORKSPACE,
            brand_id=BRAND,
            expected_policy_version=2,
            remediation_policy_version=2,
        )
    with pytest.raises(QualityPolicyGovernanceError, match="cross-scope"):
        validate_governance_case_opening(
            remediation_status=AIQualityPolicyRemediationStatus.failed,
            remediation_workspace_id=WORKSPACE,
            remediation_brand_id=BRAND,
            workspace_id=UUID("10000000-0000-0000-0000-000000000002"),
            brand_id=BRAND,
            expected_policy_version=2,
            remediation_policy_version=2,
        )


def test_case_opening_and_closure_fail_closed_on_concurrency() -> None:
    with pytest.raises(GovernanceConcurrencyConflict, match="policy version"):
        validate_governance_case_opening(
            remediation_status=AIQualityPolicyRemediationStatus.recovered,
            remediation_workspace_id=WORKSPACE,
            remediation_brand_id=BRAND,
            workspace_id=WORKSPACE,
            brand_id=BRAND,
            expected_policy_version=3,
            remediation_policy_version=2,
        )
    with pytest.raises(GovernanceConcurrencyConflict, match="manifest changed"):
        plan_governance_case_closure(
            current_status=AIQualityPolicyGovernanceCaseStatus.open,
            expected_manifest_sha256="a" * 64,
            current_manifest_sha256="b" * 64,
            decision=GovernanceClosureDecision.close,
            human_confirms_closure=True,
            reason="human closure",
        )


@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        (GovernanceClosureDecision.close, AIQualityPolicyGovernanceCaseStatus.closed),
        (GovernanceClosureDecision.reject, AIQualityPolicyGovernanceCaseStatus.rejected),
        (GovernanceClosureDecision.void, AIQualityPolicyGovernanceCaseStatus.voided),
    ],
)
def test_explicit_human_closure_is_deterministic(decision, expected) -> None:
    digest = "a" * 64
    assert plan_governance_case_closure(
        current_status=AIQualityPolicyGovernanceCaseStatus.open,
        expected_manifest_sha256=digest,
        current_manifest_sha256=digest,
        decision=decision,
        human_confirms_closure=True,
        reason="human governance decision",
    ) == expected
    with pytest.raises(QualityPolicyGovernanceError, match="explicit human"):
        plan_governance_case_closure(
            current_status=AIQualityPolicyGovernanceCaseStatus.open,
            expected_manifest_sha256=digest,
            current_manifest_sha256=digest,
            decision=decision,
            human_confirms_closure=False,
            reason="human governance decision",
        )


def test_terminal_case_is_immutable() -> None:
    with pytest.raises(QualityPolicyGovernanceError, match="already terminal"):
        plan_governance_case_closure(
            current_status=AIQualityPolicyGovernanceCaseStatus.closed,
            expected_manifest_sha256="a" * 64,
            current_manifest_sha256="a" * 64,
            decision=GovernanceClosureDecision.void,
            human_confirms_closure=True,
            reason="cannot mutate terminal case",
        )
