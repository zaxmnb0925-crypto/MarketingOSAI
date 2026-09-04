from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Sequence

from app.models.ai_quality_policy_effect import AIQualityPolicyDegradationAction, AIQualityPolicyEffectState


class PolicyEffectEvaluationError(RuntimeError):
    pass


class InsufficientPolicyEffectCohort(PolicyEffectEvaluationError):
    pass


@dataclass(frozen=True)
class WorkspaceEffectAggregate:
    cohort_token: str
    observation_count: int
    quality_score_total: int
    failure_count: int
    opted_in: bool = True


@dataclass(frozen=True)
class PolicyEffectThresholds:
    minimum_distinct_workspaces: int = 3
    minimum_observations: int = 12
    maximum_workspace_contribution: int = 20
    quality_degradation_threshold: Decimal = Decimal("5.00")
    failure_rate_increase_threshold: Decimal = Decimal("0.10")
    rollback_hysteresis_windows: int = 2


@dataclass(frozen=True)
class PolicyEffectDecision:
    observation_count: int
    distinct_workspace_count: int
    observed_quality_score: Decimal
    observed_failure_rate: Decimal
    quality_delta: Decimal
    state: AIQualityPolicyEffectState
    recommended_action: AIQualityPolicyDegradationAction
    reason: str
    confidence_score: int
    requires_human_review: bool = True
    automatic_action_performed: bool = False


def evaluate_policy_effect(
    aggregates: Sequence[WorkspaceEffectAggregate], *, baseline_quality_score: Decimal,
    baseline_failure_rate: Decimal, consecutive_degraded_windows: int = 0,
    thresholds: PolicyEffectThresholds | None = None,
) -> PolicyEffectDecision:
    policy = thresholds or PolicyEffectThresholds()
    included = [item for item in aggregates if item.opted_in]
    if len({item.cohort_token for item in included}) != len(included):
        raise PolicyEffectEvaluationError("duplicate aggregate cohort token")
    if len(included) < policy.minimum_distinct_workspaces:
        raise InsufficientPolicyEffectCohort("distinct workspace threshold not met")
    count = quality_total = failures = 0
    for item in included:
        if item.observation_count <= 0 or not 0 <= item.failure_count <= item.observation_count:
            raise PolicyEffectEvaluationError("aggregate contribution is invalid")
        if not 0 <= item.quality_score_total <= item.observation_count * 100:
            raise PolicyEffectEvaluationError("quality aggregate is invalid")
        clipped = min(item.observation_count, policy.maximum_workspace_contribution)
        ratio = Decimal(clipped) / Decimal(item.observation_count)
        count += clipped
        quality_total += round(Decimal(item.quality_score_total) * ratio)
        failures += round(Decimal(item.failure_count) * ratio)
    if count < policy.minimum_observations:
        raise InsufficientPolicyEffectCohort("observation threshold not met")
    quality = (Decimal(quality_total) / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    failure_rate = (Decimal(failures) / count).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    delta = (quality - baseline_quality_score).quantize(Decimal("0.01"))
    degraded = delta <= -policy.quality_degradation_threshold or failure_rate - baseline_failure_rate >= policy.failure_rate_increase_threshold
    if degraded and consecutive_degraded_windows + 1 >= policy.rollback_hysteresis_windows:
        state, action, reason = AIQualityPolicyEffectState.degraded, AIQualityPolicyDegradationAction.rollback, "sustained_policy_effect_degradation"
    elif degraded:
        state, action, reason = AIQualityPolicyEffectState.watch, AIQualityPolicyDegradationAction.investigate, "policy_effect_degradation_watch"
    else:
        state, action, reason = AIQualityPolicyEffectState.stable, AIQualityPolicyDegradationAction.no_change, "policy_effect_stable"
    confidence = min(100, 50 + min(count, policy.minimum_observations * 2) * 25 // policy.minimum_observations)
    return PolicyEffectDecision(count, len(included), quality, failure_rate, delta, state, action, reason, confidence)
