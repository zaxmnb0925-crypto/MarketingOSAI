from uuid import UUID
import inspect

import pytest

from app.api import content
from app.models.ai_quality_policy_activation import AIQualityPolicyActivationStatus
from app.models.ai_quality_policy_effect import AIQualityPolicyDegradationAction, AIQualityPolicyDegradationStatus
from app.models.ai_quality_policy_remediation import AIQualityPolicyRemediationStatus
from app.services.ai_quality_policy_remediation import (
    QualityPolicyRemediationError,
    RemediationConcurrencyConflict,
    RemediationDecision,
    RemediationScopeSnapshot,
    plan_recovery_closure,
    plan_remediation_decision,
    validate_remediation_execution,
    validate_remediation_proposal,
)


SOURCE = UUID("00000000-0000-0000-0000-000000000001")
TARGET = UUID("00000000-0000-0000-0000-000000000002")


def test_proposal_requires_human_accepted_rollback_recommendation():
    validate_remediation_proposal(
        degradation_status=AIQualityPolicyDegradationStatus.accepted,
        degradation_action=AIQualityPolicyDegradationAction.rollback,
        degradation_activation_id=SOURCE,
        expected_active_activation_id=SOURCE,
        target_activation_id=TARGET,
        target_policy_version=1,
    )
    with pytest.raises(QualityPolicyRemediationError):
        validate_remediation_proposal(
            degradation_status=AIQualityPolicyDegradationStatus.pending_review,
            degradation_action=AIQualityPolicyDegradationAction.rollback,
            degradation_activation_id=SOURCE,
            expected_active_activation_id=SOURCE,
            target_activation_id=TARGET,
            target_policy_version=1,
        )


def test_decision_is_explicit_and_terminal():
    assert plan_remediation_decision(
        current_status=AIQualityPolicyRemediationStatus.proposed,
        decision=RemediationDecision.approve,
    ) == AIQualityPolicyRemediationStatus.approved
    with pytest.raises(QualityPolicyRemediationError):
        plan_remediation_decision(
            current_status=AIQualityPolicyRemediationStatus.approved,
            decision=RemediationDecision.reject,
        )


def test_execution_fails_closed_on_activation_or_version_change():
    snapshot = RemediationScopeSnapshot(
        SOURCE, 4, AIQualityPolicyActivationStatus.active,
    )
    validate_remediation_execution(
        remediation_status=AIQualityPolicyRemediationStatus.approved,
        expected_source_activation_id=SOURCE,
        expected_policy_version=4,
        current=snapshot,
    )
    with pytest.raises(RemediationConcurrencyConflict):
        validate_remediation_execution(
            remediation_status=AIQualityPolicyRemediationStatus.approved,
            expected_source_activation_id=SOURCE,
            expected_policy_version=3,
            current=snapshot,
        )


def test_recovery_requires_complete_window_threshold_and_human_confirmation():
    assert plan_recovery_closure(
        remediation_status=AIQualityPolicyRemediationStatus.observation,
        observed_window_count=3,
        required_window_count=3,
        observed_quality_score=82,
        recovery_threshold=75,
        human_confirms_recovery=True,
    ) == AIQualityPolicyRemediationStatus.recovered
    for kwargs in (
        {"observed_window_count": 2, "observed_quality_score": 82, "human_confirms_recovery": True},
        {"observed_window_count": 3, "observed_quality_score": 70, "human_confirms_recovery": True},
        {"observed_window_count": 3, "observed_quality_score": 82, "human_confirms_recovery": False},
    ):
        with pytest.raises(QualityPolicyRemediationError):
            plan_recovery_closure(
                remediation_status=AIQualityPolicyRemediationStatus.observation,
                required_window_count=3,
                recovery_threshold=75,
                **kwargs,
            )


def test_api_is_workspace_brand_scoped_locked_and_human_gated():
    functions = (
        content.propose_quality_policy_remediation,
        content.decide_quality_policy_remediation,
        content.confirm_quality_policy_remediation_execution,
        content.close_quality_policy_remediation,
    )
    source = "\n".join(inspect.getsource(function) for function in functions)
    assert "workspace_id == workspace_id" in source
    assert "brand_id == brand_id" in source
    assert "with_for_update" in source
    assert "require_workspace_write" in source
    assert "human_confirms_recovery" in source
    assert "rolled_back_to_activation_id" in source


def test_service_has_no_transport_or_automatic_policy_mutation():
    import app.services.ai_quality_policy_remediation as service

    source = inspect.getsource(service).lower()
    for forbidden in (
        "httpx", "requests.", "aiohttp", "openai", "redis",
        "activate_quality_policy", "rollback_quality_policy_activation",
        "automatic_rollback", "automatic_deactivation",
    ):
        assert forbidden not in source
