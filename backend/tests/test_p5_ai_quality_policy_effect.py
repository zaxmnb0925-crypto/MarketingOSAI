from decimal import Decimal
import inspect

import pytest

from app.api import content
from app.models.ai_quality_policy_effect import (
    AIQualityPolicyDegradationAction,
    AIQualityPolicyEffectState,
)
from app.services.ai_quality_policy_effect import (
    InsufficientPolicyEffectCohort,
    WorkspaceEffectAggregate,
    evaluate_policy_effect,
)


def aggregates(*, quality=80, failures=1):
    return [
        WorkspaceEffectAggregate(f"cohort-{index}", 6, quality * 6, failures)
        for index in range(3)
    ]


def test_stable_effect_never_performs_automatic_action():
    decision = evaluate_policy_effect(
        aggregates(), baseline_quality_score=Decimal("78"),
        baseline_failure_rate=Decimal("0.20"),
    )
    assert decision.state == AIQualityPolicyEffectState.stable
    assert decision.recommended_action == AIQualityPolicyDegradationAction.no_change
    assert decision.requires_human_review is True
    assert decision.automatic_action_performed is False


def test_hysteresis_requires_sustained_degradation_before_rollback_recommendation():
    first = evaluate_policy_effect(
        aggregates(quality=60, failures=3),
        baseline_quality_score=Decimal("80"),
        baseline_failure_rate=Decimal("0.10"),
    )
    assert first.state == AIQualityPolicyEffectState.watch
    assert first.recommended_action == AIQualityPolicyDegradationAction.investigate
    second = evaluate_policy_effect(
        aggregates(quality=60, failures=3),
        baseline_quality_score=Decimal("80"),
        baseline_failure_rate=Decimal("0.10"),
        consecutive_degraded_windows=1,
    )
    assert second.state == AIQualityPolicyEffectState.degraded
    assert second.recommended_action == AIQualityPolicyDegradationAction.rollback
    assert second.automatic_action_performed is False


def test_opt_out_clipping_and_minimum_cohort_fail_closed():
    data = aggregates() + [WorkspaceEffectAggregate("opted-out", 100, 0, 100, False)]
    decision = evaluate_policy_effect(
        data, baseline_quality_score=Decimal("80"),
        baseline_failure_rate=Decimal("0.10"),
    )
    assert decision.distinct_workspace_count == 3
    with pytest.raises(InsufficientPolicyEffectCohort):
        evaluate_policy_effect(
            data[:2], baseline_quality_score=Decimal("80"),
            baseline_failure_rate=Decimal("0.10"),
        )


def test_effect_api_is_workspace_brand_scoped_and_human_reviewed():
    source = inspect.getsource(content.review_quality_policy_degradation_recommendation)
    assert "workspace_id == workspace_id" in source
    assert "brand_id == brand_id" in source
    assert "with_for_update" in source
    assert "require_workspace_write" in source
    assert "pending_review" in source


def test_service_has_no_raw_data_transport_or_automatic_policy_mutation():
    import app.services.ai_quality_policy_effect as service

    source = inspect.getsource(service).lower()
    for forbidden in (
        "httpx", "requests.", "aiohttp", "openai", "redis",
        "raw_prompt", "raw_response", "customer_content", "feedback_comment",
        "activate_quality_policy", "plan_policy_rollback",
    ):
        assert forbidden not in source
