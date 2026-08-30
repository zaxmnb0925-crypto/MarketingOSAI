from datetime import datetime, timedelta, timezone
import inspect
from uuid import uuid4

import pytest

from app.api import content
from app.models.ai_quality_policy import AIQualityPolicyStatus
from app.models.ai_quality_policy_activation import (
    AIQualityPolicyActivationMode,
    AIQualityPolicyActivationStatus,
)
from app.schemas.content import AIQualityPolicyActivationRequest
from app.services.ai_quality_policy_activation import (
    ActivationConcurrencyConflict,
    ActivationSnapshot,
    QualityPolicyActivationError,
    plan_policy_activation,
    plan_policy_rollback,
    resolve_active_policy,
    validate_activation_window,
)


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def snapshot(*, mode=AIQualityPolicyActivationMode.shadow):
    return ActivationSnapshot(
        id=uuid4(),
        recommendation_id=uuid4(),
        policy_version=3,
        mode=mode,
        status=AIQualityPolicyActivationStatus.active,
        effective_at=NOW,
    )


def test_initial_activation_requires_approved_recommendation_and_shadow():
    recommendation_id = uuid4()
    with pytest.raises(QualityPolicyActivationError):
        plan_policy_activation(
            recommendation_id=recommendation_id,
            recommendation_version=1,
            recommendation_status=AIQualityPolicyStatus.candidate,
            requested_mode=AIQualityPolicyActivationMode.shadow,
            current=None,
            expected_active_activation_id=None,
        )
    with pytest.raises(QualityPolicyActivationError):
        plan_policy_activation(
            recommendation_id=recommendation_id,
            recommendation_version=1,
            recommendation_status=AIQualityPolicyStatus.approved,
            requested_mode=AIQualityPolicyActivationMode.enforced,
            current=None,
            expected_active_activation_id=None,
        )


def test_shadow_must_precede_matching_enforced_policy():
    current = snapshot()
    plan = plan_policy_activation(
        recommendation_id=current.recommendation_id,
        recommendation_version=current.policy_version,
        recommendation_status=AIQualityPolicyStatus.approved,
        requested_mode=AIQualityPolicyActivationMode.enforced,
        current=current,
        expected_active_activation_id=current.id,
    )
    assert plan.action == "promoted"
    assert plan.supersedes_activation_id == current.id


def test_optimistic_concurrency_fails_closed():
    current = snapshot()
    with pytest.raises(ActivationConcurrencyConflict):
        plan_policy_activation(
            recommendation_id=current.recommendation_id,
            recommendation_version=current.policy_version,
            recommendation_status=AIQualityPolicyStatus.approved,
            requested_mode=AIQualityPolicyActivationMode.enforced,
            current=current,
            expected_active_activation_id=uuid4(),
        )
    assert current.status == AIQualityPolicyActivationStatus.active


def test_rollback_requires_known_prior_policy_and_exact_current_version():
    current = snapshot(mode=AIQualityPolicyActivationMode.enforced)
    target = ActivationSnapshot(
        id=uuid4(),
        recommendation_id=uuid4(),
        policy_version=2,
        mode=AIQualityPolicyActivationMode.shadow,
        status=AIQualityPolicyActivationStatus.superseded,
        effective_at=NOW,
    )
    plan = plan_policy_rollback(
        current=current,
        target=target,
        expected_active_activation_id=current.id,
    )
    assert plan.action == "rolled_back"
    assert plan.mode == AIQualityPolicyActivationMode.shadow
    with pytest.raises(ActivationConcurrencyConflict):
        plan_policy_rollback(
            current=current,
            target=target,
            expected_active_activation_id=uuid4(),
        )


def test_resolution_is_effective_expiry_aware_and_rejects_ambiguity():
    active = snapshot()
    assert resolve_active_policy([active], at=NOW + timedelta(seconds=1)) == active
    expired = ActivationSnapshot(
        **{**active.__dict__, "id": uuid4(), "expires_at": NOW + timedelta(seconds=2)}
    )
    assert resolve_active_policy([expired], at=NOW + timedelta(seconds=3)) is None
    with pytest.raises(QualityPolicyActivationError):
        resolve_active_policy([active, snapshot()], at=NOW + timedelta(seconds=1))


def test_activation_window_is_bounded_and_timezone_aware():
    validate_activation_window(NOW, NOW + timedelta(days=1))
    with pytest.raises(QualityPolicyActivationError):
        validate_activation_window(NOW, NOW)
    with pytest.raises(QualityPolicyActivationError):
        validate_activation_window(datetime(2026, 1, 1), None)


def test_activation_request_is_bounded():
    request = AIQualityPolicyActivationRequest(
        mode=AIQualityPolicyActivationMode.shadow,
        idempotency_key="human-action-0001",
        effective_at=NOW,
        reason="human-controlled shadow activation",
    )
    assert request.mode == AIQualityPolicyActivationMode.shadow
    with pytest.raises(ValueError):
        AIQualityPolicyActivationRequest(
            mode=AIQualityPolicyActivationMode.shadow,
            idempotency_key="short",
            effective_at=NOW,
            reason="valid reason",
        )


def test_activation_api_is_scoped_locked_idempotent_and_audited():
    source = inspect.getsource(content.activate_quality_policy_recommendation)
    assert "workspace_id == workspace_id" in source
    assert "brand_id == brand_id" in source
    assert source.count("with_for_update") >= 2
    assert "idempotency_key" in source
    assert "AIQualityPolicyActivationAudit" in source
    assert "plan_policy_activation" in source
    assert "require_workspace_write" in source


def test_activation_service_has_no_external_or_automatic_mutation_transport():
    import app.services.ai_quality_policy_activation as service

    source = inspect.getsource(service).lower()
    for forbidden in (
        "httpx", "requests.", "aiohttp", "openai", "redis",
        "raw_prompt", "raw_response", "customer_content", "model_provider",
    ):
        assert forbidden not in source
