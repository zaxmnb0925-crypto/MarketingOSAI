from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.models.ai_quality_policy import AIQualityPolicyStatus
from app.models.ai_quality_policy_activation import (
    AIQualityPolicyActivationMode,
    AIQualityPolicyActivationStatus,
)


class QualityPolicyActivationError(RuntimeError):
    """A controlled activation cannot be planned safely."""


class ActivationConcurrencyConflict(QualityPolicyActivationError):
    pass


@dataclass(frozen=True)
class ActivationSnapshot:
    id: UUID
    recommendation_id: UUID
    policy_version: int
    mode: AIQualityPolicyActivationMode
    status: AIQualityPolicyActivationStatus
    effective_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True)
class ActivationPlan:
    mode: AIQualityPolicyActivationMode
    supersedes_activation_id: UUID | None
    action: str


def plan_policy_rollback(
    *,
    current: ActivationSnapshot | None,
    target: ActivationSnapshot,
    expected_active_activation_id: UUID,
) -> ActivationPlan:
    if current is None or current.id != expected_active_activation_id:
        raise ActivationConcurrencyConflict("active policy changed")
    if current.status != AIQualityPolicyActivationStatus.active:
        raise QualityPolicyActivationError("current policy is not active")
    if target.id == current.id:
        raise QualityPolicyActivationError("rollback target is current policy")
    if target.status == AIQualityPolicyActivationStatus.active:
        raise QualityPolicyActivationError("rollback target must be a known prior policy")
    return ActivationPlan(target.mode, current.id, "rolled_back")


def plan_policy_activation(
    *,
    recommendation_id: UUID,
    recommendation_version: int,
    recommendation_status: AIQualityPolicyStatus,
    requested_mode: AIQualityPolicyActivationMode,
    current: ActivationSnapshot | None,
    expected_active_activation_id: UUID | None,
) -> ActivationPlan:
    if recommendation_status != AIQualityPolicyStatus.approved:
        raise QualityPolicyActivationError("recommendation is not approved")
    if recommendation_version <= 0:
        raise QualityPolicyActivationError("policy version is invalid")
    actual = current.id if current else None
    if actual != expected_active_activation_id:
        raise ActivationConcurrencyConflict("active policy changed")
    if current is None:
        if requested_mode != AIQualityPolicyActivationMode.shadow:
            raise QualityPolicyActivationError("initial activation must be shadow")
        return ActivationPlan(requested_mode, None, "activated")
    if current.status != AIQualityPolicyActivationStatus.active:
        raise QualityPolicyActivationError("current policy is not active")
    if requested_mode == AIQualityPolicyActivationMode.enforced:
        if current.mode != AIQualityPolicyActivationMode.shadow:
            raise QualityPolicyActivationError("enforced policy requires active shadow")
        if current.recommendation_id != recommendation_id:
            raise QualityPolicyActivationError("shadow recommendation mismatch")
        if current.policy_version != recommendation_version:
            raise QualityPolicyActivationError("shadow policy version mismatch")
        return ActivationPlan(requested_mode, current.id, "promoted")
    return ActivationPlan(requested_mode, current.id, "superseded")


def resolve_active_policy(
    candidates: list[ActivationSnapshot],
    *,
    at: datetime | None = None,
) -> ActivationSnapshot | None:
    moment = at or datetime.now(timezone.utc)
    eligible = [
        item for item in candidates
        if item.status == AIQualityPolicyActivationStatus.active
        and item.effective_at <= moment
        and (item.expires_at is None or moment < item.expires_at)
    ]
    if len(eligible) > 1:
        raise QualityPolicyActivationError("multiple active policies in scope")
    return eligible[0] if eligible else None


def validate_activation_window(
    effective_at: datetime,
    expires_at: datetime | None,
) -> None:
    if effective_at.tzinfo is None:
        raise QualityPolicyActivationError("effective time must be timezone aware")
    if expires_at is not None:
        if expires_at.tzinfo is None or expires_at <= effective_at:
            raise QualityPolicyActivationError("activation expiry is invalid")
