from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import (
    require_workspace_membership,
    require_workspace_write,
)
from app.core.database import get_db
from app.models.brand import Brand
from app.models.content_generation import (
    ContentGeneration,
    ContentStatus,
)
from app.models.user import User
from app.schemas.content import (
    ContentGenerationResponse,
    ContentPreviewRequest,
    CustomerContentGenerationResponse,
    GenerateContentResponse,
    PromptPreviewResponse,
)
from app.services.ai_content import (
    generate_social_content,
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
    )

    user_input_text = " ".join(
        item
        for item in [
            payload.topic,
            payload.objective,
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

    prompt = build_brand_prompt(
        brand=brand,
        platform=payload.platform,
        topic=payload.topic,
        objective=payload.objective,
    )

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

        if output_forbidden_hits:
            await refund_credits(
                db,
                workspace_id,
                CONTENT_GENERATION_CREDITS,
                generation_id=generation_id,
                operation="content_policy_refund",
                note=(
                    "Refund: generated output failed brand policy"
                ),
            )

        await record_actual_cost(
            db,
            debit_ledger_id,
            result.estimated_cost_usd,
        )

        if output_forbidden_hits:
            locked_generation.status = ContentStatus.failed
            locked_generation.error_message = (
                "Generated content contains forbidden brand terms"
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
