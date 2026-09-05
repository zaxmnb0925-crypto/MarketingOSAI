from decimal import Decimal
import inspect

import pytest

from app.api import content
from app.models.ai_quality_policy import AIQualityPolicyStatus
from app.schemas.content import AIQualityPolicyDecisionRequest
from app.services.ai_quality_policy import (
    DeterministicFakeQualityPolicyOptimizer,
    InsufficientQualityCohort,
    QualityPolicyOptimizationPolicy,
    WorkspaceQualityAggregate,
    recommend_quality_policy,
)


def aggregate(
    token: str,
    count: int,
    quality: int,
    rating: str,
    *,
    opted_in: bool = True,
) -> WorkspaceQualityAggregate:
    return WorkspaceQualityAggregate(
        cohort_token=token,
        observation_count=count,
        quality_score_total=quality * count,
        rating_total=Decimal(rating) * count,
        opted_in=opted_in,
    )


@pytest.mark.asyncio
async def test_policy_recommendation_is_deterministic_clipped_and_explainable():
    values = [
        aggregate("a", 100, 50, "2.00"),
        aggregate("b", 6, 80, "4.00"),
        aggregate("c", 6, 80, "4.00"),
    ]
    policy = QualityPolicyOptimizationPolicy(
        minimum_observations=12,
        maximum_workspace_contribution=6,
    )
    first = await recommend_quality_policy(values, 55, policy=policy)
    second = await recommend_quality_policy(values, 55, policy=policy)
    assert first == second
    assert first.observation_count == 18
    assert first.distinct_workspace_count == 3
    assert first.minimum_quality_score == 60
    assert first.recommendation_reason == "aggregate_quality_below_floor"
    assert first.provenance == "clipped_aggregate_quality_feedback"
    assert first.requires_human_approval is True


@pytest.mark.asyncio
async def test_opt_out_and_minimum_cohort_fail_closed():
    values = [
        aggregate("a", 6, 80, "4.00"),
        aggregate("b", 6, 80, "4.00"),
        aggregate("c", 100, 5, "1.00", opted_in=False),
    ]
    with pytest.raises(InsufficientQualityCohort):
        await recommend_quality_policy(values, 55)


@pytest.mark.asyncio
async def test_high_quality_candidate_never_activates_automatically():
    values = [
        aggregate("a", 5, 90, "4.80"),
        aggregate("b", 5, 90, "4.80"),
        aggregate("c", 5, 90, "4.80"),
    ]
    result = await recommend_quality_policy(values, 60)
    assert result.minimum_quality_score == 55
    assert result.requires_human_approval is True
    assert not hasattr(result, "activated")


def test_optimizer_has_no_transport_or_raw_customer_fields():
    source = inspect.getsource(DeterministicFakeQualityPolicyOptimizer).lower()
    for forbidden in (
        "httpx",
        "requests.",
        "aiohttp",
        "openai",
        "raw_prompt",
        "raw_response",
        "customer_content",
        "feedback_comment",
    ):
        assert forbidden not in source


def test_policy_decision_api_is_workspace_scoped_and_human_governed():
    source = inspect.getsource(content.decide_quality_policy_recommendation)
    assert "workspace_id == workspace_id" in source
    assert "brand_id == brand_id" in source
    assert "with_for_update" in source
    assert "approved_by_user_id = current_user.id" in source
    assert "AIQualityPolicyDecisionAudit" in source
    assert "AIQualityPolicyStatus.rolled_back" in source
    assert "activate" not in source.lower()
    request = AIQualityPolicyDecisionRequest(
        status=AIQualityPolicyStatus.approved,
        reason="human review passed",
    )
    assert request.status == AIQualityPolicyStatus.approved
