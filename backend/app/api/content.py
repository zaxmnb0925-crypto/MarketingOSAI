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

    await db.commit()
    await db.refresh(generation)

    try:
        account, debit = await reserve_credits(
            db,
            workspace_id,
            CONTENT_GENERATION_CREDITS,
            generation_id=generation.id,
            operation="content_generation",
            note="AI social content generation",
        )

    except InsufficientAICredits:
        generation.status = ContentStatus.failed
        generation.error_message = (
            "Insufficient AI credits"
        )

        await db.commit()

        raise HTTPException(
            status_code=402,
            detail="Generation is currently unavailable",
        )
    except AICreditAccountingConflict:
        await db.rollback()

        generation_result = await db.execute(
            select(ContentGeneration).where(
                ContentGeneration.id
                == generation.id
            )
        )

        stored_generation = (
            generation_result.scalar_one()
        )

        stored_generation.status = (
            ContentStatus.failed
        )

        stored_generation.error_message = (
            "AI credit accounting conflict"
        )

        await db.commit()

        raise HTTPException(
            status_code=409,
            detail="Generation request could not be completed",
        )

    try:
        result = await generate_social_content(
            prompt
        )

        generation.generated_content = (
            result.content
        )
        generation.model = result.model
        generation.input_tokens = (
            result.input_tokens
        )
        generation.output_tokens = (
            result.output_tokens
        )
        generation.estimated_cost_usd = (
            result.estimated_cost_usd
        )

        output_forbidden_hits = (
            detect_forbidden_words(
                result.content,
                brand.forbidden_words,
            )
        )

        await record_actual_cost(
            db,
            debit.id,
            result.estimated_cost_usd,
        )

        if output_forbidden_hits:
            generation.status = (
                ContentStatus.failed
            )
            generation.error_message = (
                "Generated content contains "
                "forbidden brand terms"
            )

            await db.commit()

            await refund_credits(
                db,
                workspace_id,
                CONTENT_GENERATION_CREDITS,
                generation_id=generation.id,
                operation="content_policy_refund",
                note=(
                    "Refund: generated output "
                    "failed brand policy"
                ),
            )

        else:
            generation.status = (
                ContentStatus.completed
            )

            await db.commit()

        await db.refresh(generation)

        return GenerateContentResponse(
            generation=serialize_customer_generation(
                generation
            ),
            forbidden_word_hits=(
                output_forbidden_hits
            ),
        )

    except HTTPException:
        raise

    except AICreditAccountingConflict:
        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Generation request could not be completed",
        )

    except Exception:
        await db.rollback()

        generation_result = await db.execute(
            select(ContentGeneration).where(
                ContentGeneration.id
                == generation.id
            )
        )

        stored_generation = (
            generation_result.scalar_one()
        )

        stored_generation.status = (
            ContentStatus.failed
        )
        stored_generation.error_message = (
            "AI provider generation failed"
        )

        await db.commit()

        try:
            await refund_credits(
                db,
                workspace_id,
                CONTENT_GENERATION_CREDITS,
                generation_id=generation.id,
                operation="provider_failure_refund",
                note=(
                    "Refund: AI provider "
                    "generation failed"
                ),
            )

        except AICreditAccountingConflict:
            await db.rollback()

            raise HTTPException(
                status_code=409,
                detail="AI credit accounting conflict",
            )

        raise HTTPException(
            status_code=502,
            detail="AI generation failed",
        )
