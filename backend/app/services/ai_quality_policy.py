from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol, Sequence


class QualityPolicyOptimizationError(RuntimeError):
    """Aggregate quality inputs cannot produce a safe policy candidate."""


class InsufficientQualityCohort(QualityPolicyOptimizationError):
    pass


@dataclass(frozen=True)
class QualityPolicyOptimizationPolicy:
    minimum_distinct_workspaces: int = 3
    minimum_observations: int = 12
    maximum_workspace_contribution: int = 20
    quality_floor: int = 70
    rating_floor: Decimal = Decimal("3.50")
    adjustment_step: int = 5

    def __post_init__(self) -> None:
        if not 3 <= self.minimum_distinct_workspaces <= 100:
            raise ValueError("distinct workspace threshold is invalid")
        if not 3 <= self.minimum_observations <= 1000:
            raise ValueError("observation threshold is invalid")
        if not 1 <= self.maximum_workspace_contribution <= 100:
            raise ValueError("workspace contribution clip is invalid")
        if not 0 <= self.quality_floor <= 100:
            raise ValueError("quality floor is invalid")
        if not Decimal("1") <= self.rating_floor <= Decimal("5"):
            raise ValueError("rating floor is invalid")


@dataclass(frozen=True)
class WorkspaceQualityAggregate:
    """Internal aggregate only; raw feedback and workspace IDs are excluded."""

    cohort_token: str
    observation_count: int
    quality_score_total: int
    rating_total: Decimal
    opted_in: bool = True


@dataclass(frozen=True)
class QualityPolicyCandidate:
    minimum_quality_score: int
    minimum_cohort_size: int
    maximum_workspace_contribution: int
    observation_count: int
    distinct_workspace_count: int
    average_quality_score: Decimal
    average_rating: Decimal
    confidence_score: int
    recommendation_reason: str
    provenance: str = "clipped_aggregate_quality_feedback"
    requires_human_approval: bool = True


class QualityPolicyOptimizer(Protocol):
    async def recommend(
        self,
        aggregates: Sequence[WorkspaceQualityAggregate],
        current_minimum_quality_score: int,
        policy: QualityPolicyOptimizationPolicy,
    ) -> QualityPolicyCandidate: ...


class DeterministicFakeQualityPolicyOptimizer:
    """Offline optimizer with deterministic clipping and no provider transport."""

    async def recommend(
        self,
        aggregates: Sequence[WorkspaceQualityAggregate],
        current_minimum_quality_score: int,
        policy: QualityPolicyOptimizationPolicy,
    ) -> QualityPolicyCandidate:
        if not 0 <= current_minimum_quality_score <= 100:
            raise QualityPolicyOptimizationError("current threshold is invalid")

        included = [item for item in aggregates if item.opted_in]
        tokens = {item.cohort_token for item in included}
        if len(tokens) != len(included):
            raise QualityPolicyOptimizationError("duplicate aggregate cohort token")
        if len(included) < policy.minimum_distinct_workspaces:
            raise InsufficientQualityCohort("distinct workspace threshold not met")

        clipped_count = 0
        clipped_quality_total = Decimal("0")
        clipped_rating_total = Decimal("0")
        for item in included:
            if item.observation_count <= 0:
                raise QualityPolicyOptimizationError("empty aggregate contribution")
            if not 0 <= item.quality_score_total <= item.observation_count * 100:
                raise QualityPolicyOptimizationError("quality aggregate is invalid")
            if not (
                Decimal(item.observation_count)
                <= item.rating_total
                <= Decimal(item.observation_count * 5)
            ):
                raise QualityPolicyOptimizationError("rating aggregate is invalid")
            count = min(
                item.observation_count,
                policy.maximum_workspace_contribution,
            )
            ratio = Decimal(count) / Decimal(item.observation_count)
            clipped_count += count
            clipped_quality_total += Decimal(item.quality_score_total) * ratio
            clipped_rating_total += item.rating_total * ratio

        if clipped_count < policy.minimum_observations:
            raise InsufficientQualityCohort("observation threshold not met")

        average_quality = (clipped_quality_total / clipped_count).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        average_rating = (clipped_rating_total / clipped_count).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if average_quality < policy.quality_floor or average_rating < policy.rating_floor:
            minimum_score = min(
                95, current_minimum_quality_score + policy.adjustment_step
            )
            reason = "aggregate_quality_below_floor"
        elif average_quality >= Decimal("85") and average_rating >= Decimal("4.25"):
            minimum_score = max(
                40, current_minimum_quality_score - policy.adjustment_step
            )
            reason = "aggregate_quality_above_target"
        else:
            minimum_score = current_minimum_quality_score
            reason = "aggregate_quality_within_target"

        confidence = min(
            100,
            round(
                50
                + min(clipped_count / policy.minimum_observations, 2) * 20
                + min(
                    len(included) / policy.minimum_distinct_workspaces,
                    2,
                )
                * 5
            ),
        )
        return QualityPolicyCandidate(
            minimum_quality_score=minimum_score,
            minimum_cohort_size=policy.minimum_observations,
            maximum_workspace_contribution=policy.maximum_workspace_contribution,
            observation_count=clipped_count,
            distinct_workspace_count=len(included),
            average_quality_score=average_quality,
            average_rating=average_rating,
            confidence_score=confidence,
            recommendation_reason=reason,
        )


async def recommend_quality_policy(
    aggregates: Sequence[WorkspaceQualityAggregate],
    current_minimum_quality_score: int,
    *,
    optimizer: QualityPolicyOptimizer | None = None,
    policy: QualityPolicyOptimizationPolicy | None = None,
) -> QualityPolicyCandidate:
    adapter = optimizer or DeterministicFakeQualityPolicyOptimizer()
    effective_policy = policy or QualityPolicyOptimizationPolicy()
    try:
        return await adapter.recommend(
            aggregates,
            current_minimum_quality_score,
            effective_policy,
        )
    except QualityPolicyOptimizationError:
        raise
    except Exception as exc:
        raise QualityPolicyOptimizationError(
            "quality policy optimization failed"
        ) from exc
