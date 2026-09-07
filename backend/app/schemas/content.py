from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.content_generation import (
    ContentPlatform,
    ContentStatus,
)
from app.models.ai_answer_feedback import AnswerFeedbackReason
from app.models.ai_quality_policy import AIQualityPolicyStatus
from app.models.ai_quality_policy_activation import (
    AIQualityPolicyActivationMode,
    AIQualityPolicyActivationStatus,
)
from app.models.ai_quality_policy_effect import (
    AIQualityPolicyDegradationAction,
    AIQualityPolicyDegradationStatus,
    AIQualityPolicyEffectState,
)
from app.models.ai_quality_policy_remediation import AIQualityPolicyRemediationStatus
from app.models.ai_quality_policy_governance import AIQualityPolicyGovernanceCaseStatus
from app.services.ai_quality_policy_governance import GovernanceClosureDecision


class ContentPreviewRequest(BaseModel):
    platform: ContentPlatform

    topic: str = Field(
        min_length=1,
        max_length=500,
    )

    objective: str | None = Field(
        default=None,
        max_length=300,
    )

    audience: str | None = Field(
        default=None,
        max_length=200,
    )

    tone: str | None = Field(
        default=None,
        max_length=100,
    )

    content_length: str | None = Field(
        default="standard",
        max_length=20,
    )

    call_to_action: str | None = Field(
        default=None,
        max_length=200,
    )

    keywords: str | None = Field(
        default=None,
        max_length=300,
    )


class ContentGenerationUpdateRequest(BaseModel):
    generated_content: str


class ContentGenerationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    platform: ContentPlatform
    topic: str
    objective: str | None
    status: ContentStatus
    prompt: str | None
    generated_content: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    error_message: str | None


class CustomerContentGenerationResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    brand_id: UUID
    platform: ContentPlatform
    topic: str
    objective: str | None
    status: ContentStatus
    generated_content: str | None
    created_at: datetime
    updated_at: datetime


class PromptPreviewResponse(BaseModel):
    generation: CustomerContentGenerationResponse
    forbidden_word_hits: list[str]


class GenerateContentResponse(BaseModel):
    generation: CustomerContentGenerationResponse
    forbidden_word_hits: list[str]


class AnswerQualitySummary(BaseModel):
    score: int = Field(ge=0, le=100)
    disclosure: str | None = None


class AnswerFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    reason: AnswerFeedbackReason
    comment: str | None = Field(default=None, max_length=500)


class AnswerFeedbackResponse(BaseModel):
    generation_id: UUID
    rating: int
    reason: AnswerFeedbackReason
    comment: str | None
    updated_at: datetime


class AIQualityPolicyDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: AIQualityPolicyStatus
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRecommendationResponse(BaseModel):
    id: UUID
    version: int
    status: AIQualityPolicyStatus
    minimum_quality_score: int = Field(ge=0, le=100)
    minimum_cohort_size: int = Field(ge=3, le=1000)
    maximum_workspace_contribution: int = Field(ge=1, le=100)
    observation_count: int
    distinct_workspace_count: int
    average_quality_score: Decimal
    average_rating: Decimal
    confidence_score: int = Field(ge=0, le=100)
    recommendation_reason: str
    provenance: str
    requires_human_approval: bool = True
    activation_performed: bool = False
    approved_at: datetime | None
    created_at: datetime


class AIQualityPolicyActivationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    mode: AIQualityPolicyActivationMode
    expected_active_activation_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)
    effective_at: datetime
    expires_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyActivationResponse(BaseModel):
    id: UUID
    recommendation_id: UUID
    version: int
    policy_version: int
    mode: AIQualityPolicyActivationMode
    status: AIQualityPolicyActivationStatus
    minimum_quality_score: int = Field(ge=0, le=100)
    minimum_cohort_size: int = Field(ge=3, le=1000)
    maximum_workspace_contribution: int = Field(ge=1, le=100)
    effective_at: datetime
    expires_at: datetime | None
    supersedes_activation_id: UUID | None
    created_at: datetime


class AIQualityPolicyRollbackRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    target_activation_id: UUID
    expected_active_activation_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=100)
    effective_at: datetime
    expires_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyEffectObservationResponse(BaseModel):
    id: UUID
    activation_id: UUID
    observation_count: int
    baseline_quality_score: Decimal
    observed_quality_score: Decimal
    quality_delta: Decimal
    baseline_failure_rate: Decimal
    observed_failure_rate: Decimal
    confidence_score: int = Field(ge=0, le=100)
    consecutive_degraded_windows: int
    state: AIQualityPolicyEffectState
    provenance: str
    window_started_at: datetime
    window_ended_at: datetime


class AIQualityPolicyDegradationRecommendationResponse(BaseModel):
    id: UUID
    observation_id: UUID
    activation_id: UUID
    action: AIQualityPolicyDegradationAction
    status: AIQualityPolicyDegradationStatus
    confidence_score: int = Field(ge=0, le=100)
    reason: str
    requires_human_review: bool = True
    automatic_action_performed: bool = False
    reviewed_at: datetime | None


class AIQualityPolicyDegradationReviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: AIQualityPolicyDegradationStatus
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRemediationProposalRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    degradation_recommendation_id: UUID
    source_activation_id: UUID
    target_activation_id: UUID
    expected_policy_version: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    observation_window_count: int = Field(ge=1, le=100)
    recovery_threshold: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRemediationDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    approve: bool
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRemediationExecutionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    result_activation_id: UUID
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRemediationClosureRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    observed_window_count: int = Field(ge=0, le=100)
    observed_quality_score: int = Field(ge=0, le=100)
    human_confirms_recovery: bool
    reason: str = Field(min_length=1, max_length=200)


class AIQualityPolicyRemediationResponse(BaseModel):
    id: UUID
    degradation_recommendation_id: UUID
    source_activation_id: UUID
    target_activation_id: UUID
    expected_policy_version: int
    status: AIQualityPolicyRemediationStatus
    observation_window_count: int
    recovery_threshold: int
    approved_at: datetime | None
    observation_started_at: datetime | None
    observation_ended_at: datetime | None
    closed_at: datetime | None
    created_at: datetime


class AIQualityPolicyGovernanceCaseOpenRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    remediation_id: UUID
    expected_policy_version: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    reason: str = Field(min_length=1, max_length=300)


class AIQualityPolicyGovernanceCaseClosureRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    decision: GovernanceClosureDecision
    expected_manifest_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    human_confirms_closure: bool
    reason: str = Field(min_length=1, max_length=300)


class AIQualityPolicyGovernanceEvidenceItemResponse(BaseModel):
    sequence: int
    evidence_type: str
    source_table: str
    source_record_id: UUID
    source_state: str
    payload_sha256: str


class AIQualityPolicyGovernanceCaseResponse(BaseModel):
    id: UUID
    remediation_id: UUID
    activation_id: UUID
    policy_version: int
    remediation_status_snapshot: str
    status: AIQualityPolicyGovernanceCaseStatus
    evidence_manifest_sha256: str
    evidence_item_count: int
    governance_summary: dict
    closure_reason: str | None
    closed_at: datetime | None
    created_at: datetime
