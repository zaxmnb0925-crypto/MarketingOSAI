from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.models.ai_quality_policy_activation import AIQualityPolicyActivationStatus
from app.models.ai_quality_policy_effect import AIQualityPolicyDegradationAction, AIQualityPolicyDegradationStatus
from app.models.ai_quality_policy_remediation import AIQualityPolicyRemediationStatus


class QualityPolicyRemediationError(RuntimeError):
    pass


class RemediationConcurrencyConflict(QualityPolicyRemediationError):
    pass


class RemediationDecision(str, Enum):
    approve = "approve"
    reject = "reject"


@dataclass(frozen=True)
class RemediationScopeSnapshot:
    active_activation_id: UUID
    active_policy_version: int
    active_status: AIQualityPolicyActivationStatus


def validate_remediation_proposal(*, degradation_status: AIQualityPolicyDegradationStatus, degradation_action: AIQualityPolicyDegradationAction, degradation_activation_id: UUID, expected_active_activation_id: UUID, target_activation_id: UUID, target_policy_version: int) -> None:
    if degradation_status != AIQualityPolicyDegradationStatus.accepted:
        raise QualityPolicyRemediationError("degradation recommendation is not human accepted")
    if degradation_action != AIQualityPolicyDegradationAction.rollback:
        raise QualityPolicyRemediationError("degradation recommendation does not require rollback")
    if degradation_activation_id != expected_active_activation_id:
        raise RemediationConcurrencyConflict("degraded activation is no longer active")
    if target_activation_id == expected_active_activation_id:
        raise QualityPolicyRemediationError("target activation must be a known prior version")
    if target_policy_version <= 0:
        raise QualityPolicyRemediationError("target policy version is invalid")


def plan_remediation_decision(*, current_status: AIQualityPolicyRemediationStatus, decision: RemediationDecision) -> AIQualityPolicyRemediationStatus:
    if current_status != AIQualityPolicyRemediationStatus.proposed:
        raise QualityPolicyRemediationError("remediation is not awaiting human decision")
    return AIQualityPolicyRemediationStatus.approved if decision == RemediationDecision.approve else AIQualityPolicyRemediationStatus.rejected


def validate_remediation_execution(*, remediation_status: AIQualityPolicyRemediationStatus, expected_source_activation_id: UUID, expected_policy_version: int, current: RemediationScopeSnapshot) -> None:
    if remediation_status != AIQualityPolicyRemediationStatus.approved:
        raise QualityPolicyRemediationError("remediation is not human approved")
    if current.active_activation_id != expected_source_activation_id:
        raise RemediationConcurrencyConflict("active policy changed after remediation approval")
    if current.active_policy_version != expected_policy_version:
        raise RemediationConcurrencyConflict("active policy version changed after remediation approval")
    if current.active_status != AIQualityPolicyActivationStatus.active:
        raise QualityPolicyRemediationError("source activation is not active")


def plan_recovery_closure(*, remediation_status: AIQualityPolicyRemediationStatus, observed_window_count: int, required_window_count: int, observed_quality_score: int, recovery_threshold: int, human_confirms_recovery: bool) -> AIQualityPolicyRemediationStatus:
    if remediation_status != AIQualityPolicyRemediationStatus.observation:
        raise QualityPolicyRemediationError("remediation is not in observation")
    if observed_window_count < required_window_count:
        raise QualityPolicyRemediationError("recovery observation window is incomplete")
    if not 0 <= observed_quality_score <= 100:
        raise QualityPolicyRemediationError("observed quality score is invalid")
    if observed_quality_score < recovery_threshold:
        raise QualityPolicyRemediationError("recovery threshold is not met")
    if not human_confirms_recovery:
        raise QualityPolicyRemediationError("explicit human recovery confirmation required")
    return AIQualityPolicyRemediationStatus.recovered
