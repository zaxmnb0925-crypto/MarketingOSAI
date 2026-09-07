from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import (
    require_workspace_membership,
    require_workspace_write,
)
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.models.brand import Brand
from app.models.content_generation import (
    ContentGeneration,
    ContentStatus,
)
from app.models.user import User
from app.models.ai_answer_feedback import AIAnswerFeedback
from app.models.ai_quality_policy import (
    AIQualityPolicyDecisionAudit,
    AIQualityPolicyRecommendation,
    AIQualityPolicyStatus,
)
from app.models.ai_quality_policy_activation import (
    AIQualityPolicyActivation,
    AIQualityPolicyActivationAction,
    AIQualityPolicyActivationAudit,
    AIQualityPolicyActivationStatus,
)
from app.models.ai_quality_policy_effect import (
    AIQualityPolicyDegradationRecommendation,
    AIQualityPolicyDegradationStatus,
    AIQualityPolicyEffectObservation,
)
from app.models.ai_quality_policy_remediation import (
    AIQualityPolicyRemediation,
    AIQualityPolicyRemediationAction,
    AIQualityPolicyRemediationAudit,
    AIQualityPolicyRemediationStatus,
)
from app.models.ai_quality_policy_governance import (
    AIQualityPolicyGovernanceCase,
    AIQualityPolicyGovernanceCaseAction,
    AIQualityPolicyGovernanceCaseAudit,
    AIQualityPolicyGovernanceCaseStatus,
    AIQualityPolicyGovernanceEvidenceItem,
    AIQualityPolicyGovernanceEvidenceType,
)
from app.schemas.content import (
    ContentGenerationResponse,
    ContentGenerationUpdateRequest,
    ContentPreviewRequest,
    CustomerContentGenerationResponse,
    GenerateContentResponse,
    PromptPreviewResponse,
    AnswerFeedbackRequest,
    AnswerFeedbackResponse,
    AIQualityPolicyDecisionRequest,
    AIQualityPolicyRecommendationResponse,
    AIQualityPolicyActivationRequest,
    AIQualityPolicyActivationResponse,
    AIQualityPolicyRollbackRequest,
    AIQualityPolicyDegradationRecommendationResponse,
    AIQualityPolicyDegradationReviewRequest,
    AIQualityPolicyEffectObservationResponse,
    AIQualityPolicyRemediationClosureRequest,
    AIQualityPolicyRemediationDecisionRequest,
    AIQualityPolicyRemediationExecutionRequest,
    AIQualityPolicyRemediationProposalRequest,
    AIQualityPolicyRemediationResponse,
    AIQualityPolicyGovernanceCaseClosureRequest,
    AIQualityPolicyGovernanceCaseOpenRequest,
    AIQualityPolicyGovernanceCaseResponse,
)
from app.schemas.keyword_intelligence import (
    IntelligenceContextQueryParameters,
)
from app.services.ai_answer_orchestration import (
    IntelligenceContextAssemblyError,
    prepare_ai_answer,
)
from app.services.ai_content import (
    generate_social_content,
)
from app.services.ai_answer_quality import (
    AnswerQualityContext,
    AnswerQualityEvaluationError,
    evaluate_ai_answer,
)
from app.services.ai_quality_policy_activation import (
    ActivationSnapshot,
    QualityPolicyActivationError,
    plan_policy_activation,
    plan_policy_rollback,
    validate_activation_window,
)
from app.services.ai_quality_policy_remediation import (
    QualityPolicyRemediationError,
    RemediationDecision,
    RemediationScopeSnapshot,
    plan_recovery_closure,
    plan_remediation_decision,
    validate_remediation_execution,
    validate_remediation_proposal,
)
from app.services.ai_quality_policy_governance import (
    GovernanceConcurrencyConflict,
    GovernanceEvidenceInput,
    QualityPolicyGovernanceError,
    build_governance_evidence_manifest,
    plan_governance_case_closure,
    validate_governance_case_opening,
)
from app.services.ai_credits import (
    AICreditAccountingConflict,
    CONTENT_GENERATION_CREDITS,
    InsufficientAICredits,
    record_actual_cost,
    refund_credits,
    reserve_credits,
)
from app.services.content_prompt import (
    build_brand_prompt,
    detect_forbidden_words,
)


router = APIRouter(
    prefix=(
        "/api/workspaces/{workspace_id}"
        "/brands/{brand_id}/content"
    ),
    tags=["AI Content"],
)


def serialize_generation(
    item: ContentGeneration,
) -> ContentGenerationResponse:

    return ContentGenerationResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        brand_id=item.brand_id,
        platform=item.platform,
        topic=item.topic,
        objective=item.objective,
        status=item.status,
        prompt=item.prompt,
        generated_content=item.generated_content,
        model=item.model,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        estimated_cost_usd=item.estimated_cost_usd,
        error_message=item.error_message,
    )


def serialize_customer_generation(
    item: ContentGeneration,
) -> CustomerContentGenerationResponse:
    return CustomerContentGenerationResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        brand_id=item.brand_id,
        platform=item.platform,
        topic=item.topic,
        objective=item.objective,
        status=item.status,
        generated_content=item.generated_content,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def get_brand_for_workspace(
    db: AsyncSession,
    workspace_id: UUID,
    brand_id: UUID,
) -> Brand:

    result = await db.execute(
        select(Brand).where(
            Brand.id == brand_id,
            Brand.workspace_id == workspace_id,
        )
    )

    brand = result.scalar_one_or_none()

    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    return brand


async def _lock_pending_generation(
    db: AsyncSession,
    workspace_id: UUID,
    generation_id: UUID,
) -> ContentGeneration:
    result = await db.execute(
        select(ContentGeneration)
        .where(
            ContentGeneration.id == generation_id,
            ContentGeneration.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    generation = result.scalar_one()
    if generation.status != ContentStatus.pending:
        raise AICreditAccountingConflict(
            "Content generation is already terminal"
        )
    return generation


@router.post(
    "/preview",
    response_model=PromptPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def preview_content(
    workspace_id: UUID,
    brand_id: UUID,
    payload: ContentPreviewRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    brand = await get_brand_for_workspace(
        db,
        workspace_id,
        brand_id,
    )

    prompt = build_brand_prompt(
        brand=brand,
        platform=payload.platform,
        topic=payload.topic,
        objective=payload.objective,
        audience=payload.audience,
        tone=payload.tone,
        content_length=payload.content_length,
        call_to_action=payload.call_to_action,
        keywords=payload.keywords,
    )

    user_input_text = " ".join(
        item
        for item in [
            payload.topic,
            payload.objective,
            payload.audience,
            payload.tone,
            payload.call_to_action,
            payload.keywords,
        ]
        if item
    )

    forbidden_hits = detect_forbidden_words(
        user_input_text,
        brand.forbidden_words,
    )

    generation = ContentGeneration(
        workspace_id=workspace_id,
        brand_id=brand_id,
        user_id=current_user.id,
        platform=payload.platform,
        topic=payload.topic.strip(),
        objective=payload.objective,
        status=ContentStatus.draft,
        prompt=prompt,
    )

    db.add(generation)

    await db.commit()
    await db.refresh(generation)

    return PromptPreviewResponse(
        generation=serialize_customer_generation(
            generation
        ),
        forbidden_word_hits=forbidden_hits,
    )


@router.get(
    "",
    response_model=list[
        CustomerContentGenerationResponse
    ],
)
async def list_content_generations(
    workspace_id: UUID,
    brand_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_membership(
        db,
        current_user,
        workspace_id,
    )

    await get_brand_for_workspace(
        db,
        workspace_id,
        brand_id,
    )

    result = await db.execute(
        select(ContentGeneration)
        .where(
            ContentGeneration.workspace_id
            == workspace_id,
            ContentGeneration.brand_id
            == brand_id,
        )
        .order_by(
            ContentGeneration.created_at.desc()
        )
    )

    return [
        serialize_customer_generation(item)
        for item in result.scalars().all()
    ]


@router.post(
    "/generate",
    response_model=GenerateContentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_content(
    workspace_id: UUID,
    brand_id: UUID,
    payload: ContentPreviewRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    brand = await get_brand_for_workspace(
        db,
        workspace_id,
        brand_id,
    )

    user_input_text = " ".join(
        item
        for item in [
            payload.topic,
            payload.objective,
            payload.audience,
            payload.tone,
            payload.call_to_action,
            payload.keywords,
        ]
        if item
    )

    input_forbidden_hits = (
        detect_forbidden_words(
            user_input_text,
            brand.forbidden_words,
        )
    )

    if input_forbidden_hits:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    "Input contains forbidden "
                    "brand terms"
                ),
                "forbidden_word_hits": (
                    input_forbidden_hits
                ),
            },
        )

    base_prompt = build_brand_prompt(
        brand=brand,
        platform=payload.platform,
        topic=payload.topic,
        objective=payload.objective,
        audience=payload.audience,
        tone=payload.tone,
        content_length=payload.content_length,
        call_to_action=payload.call_to_action,
        keywords=payload.keywords,
    )

    try:
        prepared_answer = await prepare_ai_answer(
            db,
            workspace_id,
            base_prompt,
            IntelligenceContextQueryParameters(
                platform=payload.platform.value,
                language=brand.language[:20],
                query=payload.topic.strip()[:100],
            ),
        )
    except IntelligenceContextAssemblyError:
        await db.rollback()
        raise HTTPException(
            status_code=503,
            detail="AI intelligence context is unavailable",
        )

    prompt = prepared_answer.prompt

    generation = ContentGeneration(
        workspace_id=workspace_id,
        brand_id=brand_id,
        user_id=current_user.id,
        platform=payload.platform,
        topic=payload.topic.strip(),
        objective=payload.objective,
        status=ContentStatus.pending,
        prompt=prompt,
    )

    db.add(generation)
    await db.flush()

    try:
        _, debit = await reserve_credits(
            db,
            workspace_id,
            CONTENT_GENERATION_CREDITS,
            generation_id=generation.id,
            operation="content_generation",
            note="AI social content generation",
        )

        generation_id = generation.id
        debit_ledger_id = debit.id
        forbidden_words = brand.forbidden_words
        await db.commit()
    except InsufficientAICredits:
        await db.rollback()
        raise HTTPException(
            status_code=402,
            detail="Generation is currently unavailable",
        )
    except AICreditAccountingConflict:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Generation request could not be completed",
        )

    # The reservation transaction is committed above.  Provider I/O must not
    # execute while any accounting transaction or row lock is open.
    try:
        result = await generate_social_content(prompt)
    except Exception:
        try:
            locked_generation = await _lock_pending_generation(
                db,
                workspace_id,
                generation_id,
            )
            await refund_credits(
                db,
                workspace_id,
                CONTENT_GENERATION_CREDITS,
                generation_id=generation_id,
                operation="provider_failure_refund",
                note="Refund: AI provider generation failed",
            )
            locked_generation.status = ContentStatus.failed
            locked_generation.error_message = (
                "AI provider generation failed"
            )
            await db.commit()
        except AICreditAccountingConflict:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="AI credit accounting conflict",
            )
        except Exception:
            await db.rollback()
            raise

        raise HTTPException(
            status_code=502,
            detail="AI generation failed",
        )

    output_forbidden_hits = detect_forbidden_words(
        result.content,
        forbidden_words,
    )

    try:
        quality = await evaluate_ai_answer(
            result.content,
            AnswerQualityContext(
                context_item_count=prepared_answer.context_item_count,
                local_item_count=prepared_answer.local_item_count,
                collective_item_count=prepared_answer.collective_item_count,
                context_bytes=prepared_answer.context_bytes,
            ),
        )
    except AnswerQualityEvaluationError:
        try:
            locked_generation = await _lock_pending_generation(
                db, workspace_id, generation_id,
            )
            await refund_credits(
                db, workspace_id, CONTENT_GENERATION_CREDITS,
                generation_id=generation_id,
                operation="quality_evaluation_refund",
                note="Refund: generated output quality evaluation failed",
            )
            locked_generation.status = ContentStatus.failed
            locked_generation.error_message = "AI quality evaluation failed"
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        raise HTTPException(status_code=502, detail="AI quality evaluation failed")

    try:
        locked_generation = await _lock_pending_generation(
            db,
            workspace_id,
            generation_id,
        )
        locked_generation.generated_content = result.content
        locked_generation.model = result.model
        locked_generation.input_tokens = result.input_tokens
        locked_generation.output_tokens = result.output_tokens
        locked_generation.estimated_cost_usd = (
            result.estimated_cost_usd
        )
        locked_generation.quality_score = quality.overall_score
        locked_generation.quality_evaluator = quality.evaluator
        locked_generation.quality_disclosure = quality.disclosure

        quality_rejected = not quality.passed
        if output_forbidden_hits or quality_rejected:
            await refund_credits(
                db,
                workspace_id,
                CONTENT_GENERATION_CREDITS,
                generation_id=generation_id,
                operation="content_policy_refund",
                note=(
                    "Refund: generated output failed policy or quality gate"
                ),
            )

        await record_actual_cost(
            db,
            debit_ledger_id,
            result.estimated_cost_usd,
        )

        if output_forbidden_hits or quality_rejected:
            locked_generation.status = ContentStatus.failed
            locked_generation.error_message = (
                "Generated content failed policy or quality gate"
            )
        else:
            locked_generation.status = ContentStatus.completed

        await db.commit()
        await db.refresh(locked_generation)
    except AICreditAccountingConflict:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Generation request could not be completed",
        )
    except Exception:
        await db.rollback()
        raise

    return GenerateContentResponse(
        generation=serialize_customer_generation(
            locked_generation
        ),
        forbidden_word_hits=output_forbidden_hits,
    )


@router.post(
    "/{generation_id}/draft",
    response_model=CustomerContentGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_content_generation_as_draft(
    workspace_id: UUID,
    brand_id: UUID,
    generation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    source = await db.scalar(
        select(ContentGeneration).where(
            ContentGeneration.id == generation_id,
            ContentGeneration.workspace_id == workspace_id,
            ContentGeneration.brand_id == brand_id,
            ContentGeneration.status.in_(
                [
                    ContentStatus.completed,
                    ContentStatus.draft,
                ]
            ),
        )
    )

    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found",
        )

    if not source.generated_content:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generation has no editable content",
        )

    draft = ContentGeneration(
        workspace_id=workspace_id,
        brand_id=brand_id,
        user_id=current_user.id,
        platform=source.platform,
        topic=source.topic,
        objective=source.objective,
        status=ContentStatus.draft,
        prompt=source.prompt,
        generated_content=source.generated_content,
    )

    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    return serialize_customer_generation(draft)


@router.patch(
    "/{generation_id}",
    response_model=CustomerContentGenerationResponse,
)
async def update_content_generation(
    workspace_id: UUID,
    brand_id: UUID,
    generation_id: UUID,
    payload: ContentGenerationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    content = payload.generated_content.strip()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Generated content cannot be empty",
        )

    if len(content) > 20000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Generated content is too long",
        )

    brand = await get_brand_for_workspace(
        db,
        workspace_id,
        brand_id,
    )

    forbidden_hits = detect_forbidden_words(
        content,
        brand.forbidden_words,
    )

    if forbidden_hits:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "文案包含品牌禁用詞，請修改後再儲存。",
                "forbidden_word_hits": forbidden_hits,
            },
        )

    generation = await db.scalar(
        select(ContentGeneration).where(
            ContentGeneration.id == generation_id,
            ContentGeneration.workspace_id == workspace_id,
            ContentGeneration.brand_id == brand_id,
            ContentGeneration.status.in_(
                [
                    ContentStatus.completed,
                    ContentStatus.draft,
                ]
            ),
        )
    )

    if generation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found",
        )

    generation.generated_content = content
    generation.status = ContentStatus.draft

    await db.commit()
    await db.refresh(generation)

    return serialize_customer_generation(generation)


@router.put(
    "/{generation_id}/feedback",
    response_model=AnswerFeedbackResponse,
)
async def upsert_answer_feedback(
    workspace_id: UUID,
    brand_id: UUID,
    generation_id: UUID,
    payload: AnswerFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    generation = await db.scalar(
        select(ContentGeneration).where(
            ContentGeneration.id == generation_id,
            ContentGeneration.workspace_id == workspace_id,
            ContentGeneration.brand_id == brand_id,
            ContentGeneration.status == ContentStatus.completed,
        )
    )
    if generation is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    feedback = await db.scalar(
        select(AIAnswerFeedback).where(
            AIAnswerFeedback.workspace_id == workspace_id,
            AIAnswerFeedback.generation_id == generation_id,
            AIAnswerFeedback.user_id == current_user.id,
        ).with_for_update()
    )
    comment = payload.comment.strip() if payload.comment else None
    if feedback is None:
        feedback = AIAnswerFeedback(
            workspace_id=workspace_id,
            generation_id=generation_id,
            user_id=current_user.id,
            rating=payload.rating,
            reason=payload.reason,
            comment=comment,
        )
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.reason = payload.reason
        feedback.comment = comment
    await db.commit()
    await db.refresh(feedback)
    return AnswerFeedbackResponse(
        generation_id=feedback.generation_id,
        rating=feedback.rating,
        reason=feedback.reason,
        comment=feedback.comment,
        updated_at=feedback.updated_at,
    )


def serialize_quality_policy_recommendation(
    item: AIQualityPolicyRecommendation,
) -> AIQualityPolicyRecommendationResponse:
    return AIQualityPolicyRecommendationResponse(
        id=item.id,
        version=item.version,
        status=item.status,
        minimum_quality_score=item.minimum_quality_score,
        minimum_cohort_size=item.minimum_cohort_size,
        maximum_workspace_contribution=item.maximum_workspace_contribution,
        observation_count=item.observation_count,
        distinct_workspace_count=item.distinct_workspace_count,
        average_quality_score=item.average_quality_score,
        average_rating=item.average_rating,
        confidence_score=item.confidence_score,
        recommendation_reason=item.recommendation_reason,
        provenance=item.provenance,
        approved_at=item.approved_at,
    )


@router.get(
    "/quality-policy/recommendations",
    response_model=list[AIQualityPolicyRecommendationResponse],
)
async def list_quality_policy_recommendations(
    workspace_id: UUID,
    brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    result = await db.execute(
        select(AIQualityPolicyRecommendation)
        .where(
            AIQualityPolicyRecommendation.workspace_id == workspace_id,
            AIQualityPolicyRecommendation.brand_id == brand_id,
        )
        .order_by(AIQualityPolicyRecommendation.version.desc())
    )
    return [
        serialize_quality_policy_recommendation(item)
        for item in result.scalars().all()
    ]


@router.post(
    "/quality-policy/recommendations/{recommendation_id}/decision",
    response_model=AIQualityPolicyRecommendationResponse,
)
async def decide_quality_policy_recommendation(
    workspace_id: UUID,
    brand_id: UUID,
    recommendation_id: UUID,
    payload: AIQualityPolicyDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    recommendation = await db.scalar(
        select(AIQualityPolicyRecommendation)
        .where(
            AIQualityPolicyRecommendation.id == recommendation_id,
            AIQualityPolicyRecommendation.workspace_id == workspace_id,
            AIQualityPolicyRecommendation.brand_id == brand_id,
        )
        .with_for_update()
    )
    if recommendation is None:
        raise HTTPException(
            status_code=404,
            detail="Policy recommendation not found",
        )

    allowed = {
        AIQualityPolicyStatus.candidate: {
            AIQualityPolicyStatus.approved,
            AIQualityPolicyStatus.rejected,
        },
        AIQualityPolicyStatus.approved: {
            AIQualityPolicyStatus.rolled_back,
        },
    }
    if payload.status not in allowed.get(recommendation.status, set()):
        raise HTTPException(
            status_code=409,
            detail="Policy decision is not allowed",
        )

    previous_status = recommendation.status
    recommendation.status = payload.status
    if payload.status == AIQualityPolicyStatus.approved:
        recommendation.approved_by_user_id = current_user.id
        recommendation.approved_at = datetime.now(timezone.utc)
    db.add(
        AIQualityPolicyDecisionAudit(
            recommendation_id=recommendation.id,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            previous_status=previous_status,
            new_status=payload.status,
            reason=payload.reason.strip(),
        )
    )
    await db.commit()
    await db.refresh(recommendation)
    return serialize_quality_policy_recommendation(recommendation)


def serialize_quality_policy_activation(
    item: AIQualityPolicyActivation,
) -> AIQualityPolicyActivationResponse:
    return AIQualityPolicyActivationResponse(
        id=item.id,
        recommendation_id=item.recommendation_id,
        version=item.version,
        policy_version=item.policy_version,
        mode=item.mode,
        status=item.status,
        minimum_quality_score=item.minimum_quality_score,
        minimum_cohort_size=item.minimum_cohort_size,
        maximum_workspace_contribution=item.maximum_workspace_contribution,
        effective_at=item.effective_at,
        expires_at=item.expires_at,
        supersedes_activation_id=item.supersedes_activation_id,
        created_at=item.created_at,
    )


def serialize_policy_effect_observation(
    item: AIQualityPolicyEffectObservation,
) -> AIQualityPolicyEffectObservationResponse:
    return AIQualityPolicyEffectObservationResponse(
        id=item.id, activation_id=item.activation_id,
        observation_count=item.observation_count,
        baseline_quality_score=item.baseline_quality_score,
        observed_quality_score=item.observed_quality_score,
        quality_delta=item.quality_delta,
        baseline_failure_rate=item.baseline_failure_rate,
        observed_failure_rate=item.observed_failure_rate,
        confidence_score=item.confidence_score,
        consecutive_degraded_windows=item.consecutive_degraded_windows,
        state=item.state, provenance=item.provenance,
        window_started_at=item.window_started_at,
        window_ended_at=item.window_ended_at,
    )


def serialize_degradation_recommendation(
    item: AIQualityPolicyDegradationRecommendation,
) -> AIQualityPolicyDegradationRecommendationResponse:
    return AIQualityPolicyDegradationRecommendationResponse(
        id=item.id, observation_id=item.observation_id,
        activation_id=item.activation_id, action=item.action,
        status=item.status, confidence_score=item.confidence_score,
        reason=item.reason, reviewed_at=item.reviewed_at,
    )


@router.get(
    "/quality-policy/effects",
    response_model=list[AIQualityPolicyEffectObservationResponse],
)
async def list_quality_policy_effects(
    workspace_id: UUID, brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    result = await db.execute(
        select(AIQualityPolicyEffectObservation).where(
            AIQualityPolicyEffectObservation.workspace_id == workspace_id,
            AIQualityPolicyEffectObservation.brand_id == brand_id,
        ).order_by(AIQualityPolicyEffectObservation.window_ended_at.desc())
    )
    return [serialize_policy_effect_observation(item) for item in result.scalars().all()]


@router.get(
    "/quality-policy/degradation-recommendations",
    response_model=list[AIQualityPolicyDegradationRecommendationResponse],
)
async def list_quality_policy_degradation_recommendations(
    workspace_id: UUID, brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    result = await db.execute(
        select(AIQualityPolicyDegradationRecommendation).where(
            AIQualityPolicyDegradationRecommendation.workspace_id == workspace_id,
            AIQualityPolicyDegradationRecommendation.brand_id == brand_id,
        ).order_by(AIQualityPolicyDegradationRecommendation.created_at.desc())
    )
    return [serialize_degradation_recommendation(item) for item in result.scalars().all()]


@router.post(
    "/quality-policy/degradation-recommendations/{degradation_id}/review",
    response_model=AIQualityPolicyDegradationRecommendationResponse,
)
async def review_quality_policy_degradation_recommendation(
    workspace_id: UUID, brand_id: UUID, degradation_id: UUID,
    payload: AIQualityPolicyDegradationReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    if payload.status not in {
        AIQualityPolicyDegradationStatus.accepted,
        AIQualityPolicyDegradationStatus.dismissed,
    }:
        raise HTTPException(status_code=422, detail="Terminal human review required")
    item = await db.scalar(
        select(AIQualityPolicyDegradationRecommendation).where(
            AIQualityPolicyDegradationRecommendation.id == degradation_id,
            AIQualityPolicyDegradationRecommendation.workspace_id == workspace_id,
            AIQualityPolicyDegradationRecommendation.brand_id == brand_id,
        ).with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Degradation recommendation not found")
    if item.status != AIQualityPolicyDegradationStatus.pending_review:
        raise HTTPException(status_code=409, detail="Recommendation already reviewed")
    item.status = payload.status
    item.reviewed_by_user_id = current_user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.review_reason = payload.reason
    await db.commit()
    await db.refresh(item)
    return serialize_degradation_recommendation(item)


def serialize_quality_policy_remediation(
    item: AIQualityPolicyRemediation,
) -> AIQualityPolicyRemediationResponse:
    return AIQualityPolicyRemediationResponse(
        id=item.id,
        degradation_recommendation_id=item.degradation_recommendation_id,
        source_activation_id=item.source_activation_id,
        target_activation_id=item.target_activation_id,
        expected_policy_version=item.expected_policy_version,
        status=item.status,
        observation_window_count=item.observation_window_count,
        recovery_threshold=item.recovery_threshold,
        approved_at=item.approved_at,
        observation_started_at=item.observation_started_at,
        observation_ended_at=item.observation_ended_at,
        closed_at=item.closed_at,
        created_at=item.created_at,
    )


def add_remediation_audit(
    db: AsyncSession, item: AIQualityPolicyRemediation,
    actor_user_id: UUID, action: AIQualityPolicyRemediationAction,
    previous_status: AIQualityPolicyRemediationStatus | None, reason: str,
) -> None:
    db.add(AIQualityPolicyRemediationAudit(
        remediation_id=item.id, workspace_id=item.workspace_id,
        actor_user_id=actor_user_id, action=action,
        previous_status=previous_status, new_status=item.status,
        reason=reason.strip(),
    ))


@router.get(
    "/quality-policy/remediations",
    response_model=list[AIQualityPolicyRemediationResponse],
)
async def list_quality_policy_remediations(
    workspace_id: UUID, brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    result = await db.execute(select(AIQualityPolicyRemediation).where(
        AIQualityPolicyRemediation.workspace_id == workspace_id,
        AIQualityPolicyRemediation.brand_id == brand_id,
    ).order_by(AIQualityPolicyRemediation.created_at.desc()))
    return [serialize_quality_policy_remediation(item) for item in result.scalars().all()]


@router.post(
    "/quality-policy/remediations",
    response_model=AIQualityPolicyRemediationResponse,
)
async def propose_quality_policy_remediation(
    workspace_id: UUID, brand_id: UUID,
    payload: AIQualityPolicyRemediationProposalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    existing = await db.scalar(select(AIQualityPolicyRemediation).where(
        AIQualityPolicyRemediation.workspace_id == workspace_id,
        AIQualityPolicyRemediation.brand_id == brand_id,
        AIQualityPolicyRemediation.idempotency_key == payload.idempotency_key,
    ))
    if existing is not None:
        if existing.degradation_recommendation_id != payload.degradation_recommendation_id:
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        return serialize_quality_policy_remediation(existing)
    degradation = await db.scalar(select(AIQualityPolicyDegradationRecommendation).where(
        AIQualityPolicyDegradationRecommendation.id == payload.degradation_recommendation_id,
        AIQualityPolicyDegradationRecommendation.workspace_id == workspace_id,
        AIQualityPolicyDegradationRecommendation.brand_id == brand_id,
    ).with_for_update())
    source = await db.scalar(select(AIQualityPolicyActivation).where(
        AIQualityPolicyActivation.id == payload.source_activation_id,
        AIQualityPolicyActivation.workspace_id == workspace_id,
        AIQualityPolicyActivation.brand_id == brand_id,
        AIQualityPolicyActivation.status == AIQualityPolicyActivationStatus.active,
    ).with_for_update())
    target = await db.scalar(select(AIQualityPolicyActivation).where(
        AIQualityPolicyActivation.id == payload.target_activation_id,
        AIQualityPolicyActivation.workspace_id == workspace_id,
        AIQualityPolicyActivation.brand_id == brand_id,
    ).with_for_update())
    if degradation is None or source is None or target is None:
        raise HTTPException(status_code=404, detail="Remediation foundation not found")
    try:
        validate_remediation_proposal(
            degradation_status=degradation.status, degradation_action=degradation.action,
            degradation_activation_id=degradation.activation_id,
            expected_active_activation_id=source.id,
            target_activation_id=target.id, target_policy_version=target.policy_version,
        )
    except QualityPolicyRemediationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if payload.expected_policy_version != source.policy_version:
        raise HTTPException(status_code=409, detail="Active policy version changed")
    item = AIQualityPolicyRemediation(
        degradation_recommendation_id=degradation.id, workspace_id=workspace_id,
        brand_id=brand_id, source_activation_id=source.id,
        target_activation_id=target.id, expected_policy_version=source.policy_version,
        status=AIQualityPolicyRemediationStatus.proposed,
        idempotency_key=payload.idempotency_key, proposal_reason=payload.reason,
        observation_window_count=payload.observation_window_count,
        recovery_threshold=payload.recovery_threshold,
        proposed_by_user_id=current_user.id,
    )
    db.add(item)
    await db.flush()
    add_remediation_audit(db, item, current_user.id, AIQualityPolicyRemediationAction.proposed, None, payload.reason)
    await db.commit()
    await db.refresh(item)
    return serialize_quality_policy_remediation(item)


@router.post(
    "/quality-policy/remediations/{remediation_id}/decision",
    response_model=AIQualityPolicyRemediationResponse,
)
async def decide_quality_policy_remediation(
    workspace_id: UUID, brand_id: UUID, remediation_id: UUID,
    payload: AIQualityPolicyRemediationDecisionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    item = await db.scalar(select(AIQualityPolicyRemediation).where(
        AIQualityPolicyRemediation.id == remediation_id,
        AIQualityPolicyRemediation.workspace_id == workspace_id,
        AIQualityPolicyRemediation.brand_id == brand_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Remediation not found")
    previous = item.status
    try:
        item.status = plan_remediation_decision(
            current_status=item.status,
            decision=RemediationDecision.approve if payload.approve else RemediationDecision.reject,
        )
    except QualityPolicyRemediationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    item.decision_reason = payload.reason
    action = AIQualityPolicyRemediationAction.approved if payload.approve else AIQualityPolicyRemediationAction.rejected
    if payload.approve:
        item.approved_by_user_id = current_user.id
        item.approved_at = datetime.now(timezone.utc)
    add_remediation_audit(db, item, current_user.id, action, previous, payload.reason)
    await db.commit()
    await db.refresh(item)
    return serialize_quality_policy_remediation(item)


@router.post(
    "/quality-policy/remediations/{remediation_id}/execution-confirmation",
    response_model=AIQualityPolicyRemediationResponse,
)
async def confirm_quality_policy_remediation_execution(
    workspace_id: UUID, brand_id: UUID, remediation_id: UUID,
    payload: AIQualityPolicyRemediationExecutionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    item = await db.scalar(select(AIQualityPolicyRemediation).where(
        AIQualityPolicyRemediation.id == remediation_id,
        AIQualityPolicyRemediation.workspace_id == workspace_id,
        AIQualityPolicyRemediation.brand_id == brand_id,
    ).with_for_update())
    result = await db.scalar(select(AIQualityPolicyActivation).where(
        AIQualityPolicyActivation.id == payload.result_activation_id,
        AIQualityPolicyActivation.workspace_id == workspace_id,
        AIQualityPolicyActivation.brand_id == brand_id,
        AIQualityPolicyActivation.status == AIQualityPolicyActivationStatus.active,
    ).with_for_update())
    if item is None or result is None:
        raise HTTPException(status_code=404, detail="Remediation execution foundation not found")
    try:
        validate_remediation_execution(
            remediation_status=item.status,
            expected_source_activation_id=item.source_activation_id,
            expected_policy_version=item.expected_policy_version,
            current=RemediationScopeSnapshot(
                active_activation_id=item.source_activation_id,
                active_policy_version=item.expected_policy_version,
                active_status=AIQualityPolicyActivationStatus.active,
            ),
        )
    except QualityPolicyRemediationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result.rolled_back_to_activation_id != item.target_activation_id:
        raise HTTPException(status_code=409, detail="P5-C8 rollback target mismatch")
    previous = item.status
    item.status = AIQualityPolicyRemediationStatus.observation
    item.execution_reason = payload.reason
    item.executed_by_user_id = current_user.id
    item.execution_started_at = datetime.now(timezone.utc)
    item.observation_started_at = datetime.now(timezone.utc)
    add_remediation_audit(db, item, current_user.id, AIQualityPolicyRemediationAction.observation_started, previous, payload.reason)
    await db.commit()
    await db.refresh(item)
    return serialize_quality_policy_remediation(item)


@router.post(
    "/quality-policy/remediations/{remediation_id}/closure",
    response_model=AIQualityPolicyRemediationResponse,
)
async def close_quality_policy_remediation(
    workspace_id: UUID, brand_id: UUID, remediation_id: UUID,
    payload: AIQualityPolicyRemediationClosureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    item = await db.scalar(select(AIQualityPolicyRemediation).where(
        AIQualityPolicyRemediation.id == remediation_id,
        AIQualityPolicyRemediation.workspace_id == workspace_id,
        AIQualityPolicyRemediation.brand_id == brand_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Remediation not found")
    previous = item.status
    try:
        item.status = plan_recovery_closure(
            remediation_status=item.status,
            observed_window_count=payload.observed_window_count,
            required_window_count=item.observation_window_count,
            observed_quality_score=payload.observed_quality_score,
            recovery_threshold=item.recovery_threshold,
            human_confirms_recovery=payload.human_confirms_recovery,
        )
    except QualityPolicyRemediationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    now = datetime.now(timezone.utc)
    item.observation_ended_at = now
    item.closed_at = now
    item.closed_by_user_id = current_user.id
    item.closure_reason = payload.reason
    add_remediation_audit(db, item, current_user.id, AIQualityPolicyRemediationAction.recovered, previous, payload.reason)
    await db.commit()
    await db.refresh(item)
    return serialize_quality_policy_remediation(item)


def serialize_quality_policy_governance_case(
    item: AIQualityPolicyGovernanceCase,
) -> AIQualityPolicyGovernanceCaseResponse:
    return AIQualityPolicyGovernanceCaseResponse(
        id=item.id,
        remediation_id=item.remediation_id,
        activation_id=item.activation_id,
        policy_version=item.policy_version,
        remediation_status_snapshot=item.remediation_status_snapshot,
        status=item.status,
        evidence_manifest_sha256=item.evidence_manifest_sha256,
        evidence_item_count=item.evidence_item_count,
        governance_summary=item.governance_summary,
        closure_reason=item.closure_reason,
        closed_at=item.closed_at,
        created_at=item.created_at,
    )


@router.get(
    "/quality-policy/governance-cases",
    response_model=list[AIQualityPolicyGovernanceCaseResponse],
)
async def list_quality_policy_governance_cases(
    workspace_id: UUID,
    brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    result = await db.execute(
        select(AIQualityPolicyGovernanceCase)
        .where(
            AIQualityPolicyGovernanceCase.workspace_id == workspace_id,
            AIQualityPolicyGovernanceCase.brand_id == brand_id,
        )
        .order_by(AIQualityPolicyGovernanceCase.created_at.desc())
    )
    return [serialize_quality_policy_governance_case(item) for item in result.scalars().all()]


@router.post(
    "/quality-policy/governance-cases",
    response_model=AIQualityPolicyGovernanceCaseResponse,
)
async def open_quality_policy_governance_case(
    workspace_id: UUID,
    brand_id: UUID,
    payload: AIQualityPolicyGovernanceCaseOpenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    existing = await db.scalar(
        select(AIQualityPolicyGovernanceCase).where(
            AIQualityPolicyGovernanceCase.workspace_id == workspace_id,
            AIQualityPolicyGovernanceCase.brand_id == brand_id,
            AIQualityPolicyGovernanceCase.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        if existing.remediation_id != payload.remediation_id:
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        return serialize_quality_policy_governance_case(existing)
    remediation = await db.scalar(
        select(AIQualityPolicyRemediation)
        .where(
            AIQualityPolicyRemediation.id == payload.remediation_id,
            AIQualityPolicyRemediation.workspace_id == workspace_id,
            AIQualityPolicyRemediation.brand_id == brand_id,
        )
        .with_for_update()
    )
    if remediation is None:
        raise HTTPException(status_code=404, detail="Remediation not found")
    degradation = await db.scalar(
        select(AIQualityPolicyDegradationRecommendation).where(
            AIQualityPolicyDegradationRecommendation.id == remediation.degradation_recommendation_id,
            AIQualityPolicyDegradationRecommendation.workspace_id == workspace_id,
            AIQualityPolicyDegradationRecommendation.brand_id == brand_id,
        )
    )
    activation = await db.scalar(
        select(AIQualityPolicyActivation).where(
            AIQualityPolicyActivation.id == remediation.target_activation_id,
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
        )
    )
    if degradation is None or activation is None:
        raise HTTPException(status_code=404, detail="Governance evidence foundation not found")
    observation = await db.scalar(
        select(AIQualityPolicyEffectObservation).where(
            AIQualityPolicyEffectObservation.id == degradation.observation_id,
            AIQualityPolicyEffectObservation.workspace_id == workspace_id,
            AIQualityPolicyEffectObservation.brand_id == brand_id,
        )
    )
    if observation is None:
        raise HTTPException(status_code=404, detail="Governance observation not found")
    try:
        validate_governance_case_opening(
            remediation_status=remediation.status,
            remediation_workspace_id=remediation.workspace_id,
            remediation_brand_id=remediation.brand_id,
            workspace_id=workspace_id,
            brand_id=brand_id,
            expected_policy_version=payload.expected_policy_version,
            remediation_policy_version=remediation.expected_policy_version,
        )
        evidence, manifest_sha = build_governance_evidence_manifest([
            GovernanceEvidenceInput("remediation", "ai_quality_policy_remediations", remediation.id, remediation.status.value, {"status": remediation.status.value, "expected_policy_version": remediation.expected_policy_version, "source_activation_id": str(remediation.source_activation_id), "target_activation_id": str(remediation.target_activation_id)}),
            GovernanceEvidenceInput("degradation", "ai_quality_policy_degradation_recommendations", degradation.id, degradation.status.value, {"status": degradation.status.value, "action": degradation.action.value, "confidence_score": degradation.confidence_score}),
            GovernanceEvidenceInput("observation", "ai_quality_policy_effect_observations", observation.id, observation.state.value, {"state": observation.state.value, "observed_quality_score": str(observation.observed_quality_score), "confidence_score": observation.confidence_score}),
            GovernanceEvidenceInput("activation", "ai_quality_policy_activations", activation.id, activation.status.value, {"status": activation.status.value, "policy_version": activation.policy_version, "mode": activation.mode.value}),
        ])
    except (QualityPolicyGovernanceError, GovernanceConcurrencyConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    summary = {
        "remediation_id": str(remediation.id),
        "remediation_status": remediation.status.value,
        "policy_version": remediation.expected_policy_version,
        "activation_id": str(activation.id),
        "evidence_manifest_sha256": manifest_sha,
        "evidence_item_count": len(evidence),
        "local_export_only": True,
        "external_transport_performed": False,
    }
    item = AIQualityPolicyGovernanceCase(
        remediation_id=remediation.id,
        workspace_id=workspace_id,
        brand_id=brand_id,
        activation_id=activation.id,
        policy_version=remediation.expected_policy_version,
        remediation_status_snapshot=remediation.status.value,
        status=AIQualityPolicyGovernanceCaseStatus.open,
        idempotency_key=payload.idempotency_key,
        evidence_manifest_sha256=manifest_sha,
        evidence_item_count=len(evidence),
        governance_summary=summary,
        created_by_user_id=current_user.id,
    )
    db.add(item)
    await db.flush()
    for snapshot in evidence:
        db.add(AIQualityPolicyGovernanceEvidenceItem(
            case_id=item.id,
            workspace_id=workspace_id,
            sequence=snapshot.sequence,
            evidence_type=AIQualityPolicyGovernanceEvidenceType(snapshot.evidence_type),
            source_table=snapshot.source_table,
            source_record_id=snapshot.source_record_id,
            source_state=snapshot.source_state,
            payload_sha256=snapshot.payload_sha256,
            payload=snapshot.payload,
        ))
    db.add(AIQualityPolicyGovernanceCaseAudit(
        case_id=item.id,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        action=AIQualityPolicyGovernanceCaseAction.opened,
        previous_status=None,
        new_status=item.status,
        reason=payload.reason,
    ))
    await db.commit()
    await db.refresh(item)
    return serialize_quality_policy_governance_case(item)


@router.post(
    "/quality-policy/governance-cases/{case_id}/closure",
    response_model=AIQualityPolicyGovernanceCaseResponse,
)
async def close_quality_policy_governance_case(
    workspace_id: UUID,
    brand_id: UUID,
    case_id: UUID,
    payload: AIQualityPolicyGovernanceCaseClosureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    item = await db.scalar(
        select(AIQualityPolicyGovernanceCase)
        .where(
            AIQualityPolicyGovernanceCase.id == case_id,
            AIQualityPolicyGovernanceCase.workspace_id == workspace_id,
            AIQualityPolicyGovernanceCase.brand_id == brand_id,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Governance case not found")
    previous = item.status
    try:
        item.status = plan_governance_case_closure(
            current_status=item.status,
            expected_manifest_sha256=payload.expected_manifest_sha256,
            current_manifest_sha256=item.evidence_manifest_sha256,
            decision=payload.decision,
            human_confirms_closure=payload.human_confirms_closure,
            reason=payload.reason,
        )
    except (QualityPolicyGovernanceError, GovernanceConcurrencyConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    item.closure_reason = payload.reason
    item.closed_by_user_id = current_user.id
    item.closed_at = datetime.now(timezone.utc)
    db.add(AIQualityPolicyGovernanceCaseAudit(
        case_id=item.id,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        action=AIQualityPolicyGovernanceCaseAction(item.status.value),
        previous_status=previous,
        new_status=item.status,
        reason=payload.reason,
    ))
    await db.commit()
    await db.refresh(item)
    return serialize_quality_policy_governance_case(item)


@router.get(
    "/quality-policy/activations/active",
    response_model=AIQualityPolicyActivationResponse | None,
)
async def get_active_quality_policy(
    workspace_id: UUID,
    brand_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    activation = await db.scalar(
        select(AIQualityPolicyActivation).where(
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
            AIQualityPolicyActivation.status == AIQualityPolicyActivationStatus.active,
            AIQualityPolicyActivation.effective_at <= datetime.now(timezone.utc),
            or_(
                AIQualityPolicyActivation.expires_at.is_(None),
                AIQualityPolicyActivation.expires_at > datetime.now(timezone.utc),
            ),
        )
    )
    return serialize_quality_policy_activation(activation) if activation else None


@router.post(
    "/quality-policy/recommendations/{recommendation_id}/activate",
    response_model=AIQualityPolicyActivationResponse,
)
async def activate_quality_policy_recommendation(
    workspace_id: UUID,
    brand_id: UUID,
    recommendation_id: UUID,
    payload: AIQualityPolicyActivationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)

    idempotent = await db.scalar(
        select(AIQualityPolicyActivation).where(
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
            AIQualityPolicyActivation.idempotency_key == payload.idempotency_key,
        )
    )
    if idempotent is not None:
        if (
            idempotent.recommendation_id != recommendation_id
            or idempotent.mode != payload.mode
        ):
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        return serialize_quality_policy_activation(idempotent)

    recommendation = await db.scalar(
        select(AIQualityPolicyRecommendation)
        .where(
            AIQualityPolicyRecommendation.id == recommendation_id,
            AIQualityPolicyRecommendation.workspace_id == workspace_id,
            AIQualityPolicyRecommendation.brand_id == brand_id,
        )
        .with_for_update()
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Policy recommendation not found")

    current = await db.scalar(
        select(AIQualityPolicyActivation)
        .where(
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
            AIQualityPolicyActivation.status == AIQualityPolicyActivationStatus.active,
        )
        .with_for_update()
    )
    snapshot = None
    if current is not None:
        snapshot = ActivationSnapshot(
            id=current.id,
            recommendation_id=current.recommendation_id,
            policy_version=current.policy_version,
            mode=current.mode,
            status=current.status,
            effective_at=current.effective_at,
            expires_at=current.expires_at,
        )
    try:
        validate_activation_window(payload.effective_at, payload.expires_at)
        plan = plan_policy_activation(
            recommendation_id=recommendation.id,
            recommendation_version=recommendation.version,
            recommendation_status=recommendation.status,
            requested_mode=payload.mode,
            current=snapshot,
            expected_active_activation_id=payload.expected_active_activation_id,
        )
    except QualityPolicyActivationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    latest_version = await db.scalar(
        select(AIQualityPolicyActivation.version)
        .where(
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
        )
        .order_by(AIQualityPolicyActivation.version.desc())
        .limit(1)
    )
    if current is not None:
        current.status = AIQualityPolicyActivationStatus.superseded
    activation = AIQualityPolicyActivation(
        workspace_id=workspace_id,
        brand_id=brand_id,
        recommendation_id=recommendation.id,
        version=(latest_version or 0) + 1,
        policy_version=recommendation.version,
        mode=plan.mode,
        status=AIQualityPolicyActivationStatus.active,
        minimum_quality_score=recommendation.minimum_quality_score,
        minimum_cohort_size=recommendation.minimum_cohort_size,
        maximum_workspace_contribution=recommendation.maximum_workspace_contribution,
        effective_at=payload.effective_at,
        expires_at=payload.expires_at,
        activated_by_user_id=current_user.id,
        idempotency_key=payload.idempotency_key,
        supersedes_activation_id=plan.supersedes_activation_id,
    )
    db.add(activation)
    await db.flush()
    db.add(
        AIQualityPolicyActivationAudit(
            activation_id=activation.id,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            action=AIQualityPolicyActivationAction(plan.action),
            previous_activation_id=current.id if current else None,
            reason=payload.reason,
        )
    )
    await db.commit()
    await db.refresh(activation)
    return serialize_quality_policy_activation(activation)


@router.post(
    "/quality-policy/activations/{activation_id}/rollback",
    response_model=AIQualityPolicyActivationResponse,
)
async def rollback_quality_policy_activation(
    workspace_id: UUID,
    brand_id: UUID,
    activation_id: UUID,
    payload: AIQualityPolicyRollbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_write(db, current_user, workspace_id)
    await get_brand_for_workspace(db, workspace_id, brand_id)
    idempotent = await db.scalar(
        select(AIQualityPolicyActivation).where(
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
            AIQualityPolicyActivation.idempotency_key == payload.idempotency_key,
        )
    )
    if idempotent is not None:
        if idempotent.rolled_back_to_activation_id != payload.target_activation_id:
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        return serialize_quality_policy_activation(idempotent)

    current = await db.scalar(
        select(AIQualityPolicyActivation)
        .where(
            AIQualityPolicyActivation.id == activation_id,
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
            AIQualityPolicyActivation.status == AIQualityPolicyActivationStatus.active,
        )
        .with_for_update()
    )
    target = await db.scalar(
        select(AIQualityPolicyActivation)
        .where(
            AIQualityPolicyActivation.id == payload.target_activation_id,
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
        )
        .with_for_update()
    )
    if current is None or target is None:
        raise HTTPException(status_code=404, detail="Activation not found")
    try:
        validate_activation_window(payload.effective_at, payload.expires_at)
        plan = plan_policy_rollback(
            current=ActivationSnapshot(
                id=current.id,
                recommendation_id=current.recommendation_id,
                policy_version=current.policy_version,
                mode=current.mode,
                status=current.status,
                effective_at=current.effective_at,
                expires_at=current.expires_at,
            ),
            target=ActivationSnapshot(
                id=target.id,
                recommendation_id=target.recommendation_id,
                policy_version=target.policy_version,
                mode=target.mode,
                status=target.status,
                effective_at=target.effective_at,
                expires_at=target.expires_at,
            ),
            expected_active_activation_id=payload.expected_active_activation_id,
        )
    except QualityPolicyActivationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    latest_version = await db.scalar(
        select(AIQualityPolicyActivation.version)
        .where(
            AIQualityPolicyActivation.workspace_id == workspace_id,
            AIQualityPolicyActivation.brand_id == brand_id,
        )
        .order_by(AIQualityPolicyActivation.version.desc())
        .limit(1)
    )
    current.status = AIQualityPolicyActivationStatus.rolled_back
    rollback = AIQualityPolicyActivation(
        workspace_id=workspace_id,
        brand_id=brand_id,
        recommendation_id=target.recommendation_id,
        version=(latest_version or 0) + 1,
        policy_version=target.policy_version,
        mode=plan.mode,
        status=AIQualityPolicyActivationStatus.active,
        minimum_quality_score=target.minimum_quality_score,
        minimum_cohort_size=target.minimum_cohort_size,
        maximum_workspace_contribution=target.maximum_workspace_contribution,
        effective_at=payload.effective_at,
        expires_at=payload.expires_at,
        activated_by_user_id=current_user.id,
        idempotency_key=payload.idempotency_key,
        supersedes_activation_id=current.id,
        rolled_back_to_activation_id=target.id,
    )
    db.add(rollback)
    await db.flush()
    db.add(AIQualityPolicyActivationAudit(
        activation_id=rollback.id,
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        action=AIQualityPolicyActivationAction.rolled_back,
        previous_activation_id=current.id,
        reason=payload.reason,
    ))
    await db.commit()
    await db.refresh(rollback)
    return serialize_quality_policy_activation(rollback)
