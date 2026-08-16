from .common import (
    APIRouter,
    AsyncSession,
    ControlledPublicationActivationRejected,
    ControlledPublicationConfirmationRejected,
    ControlledPublicationContentHashMismatch,
    ControlledPublicationExecutionDisabled,
    Depends,
    HTTPException,
    PUBLICATION_ACTIVATION_TTL_SECONDS,
    PUBLICATION_CONFIRMATION_TTL_SECONDS,
    Publication,
    PublicationActivationResponse,
    PublicationConfirmationResponse,
    PublicationDraftCreate,
    PublicationDryRunResponse,
    PublicationExecutionError,
    PublicationExecutionOutcomeUnknown,
    PublicationExecutionProviderRejected,
    PublicationIdempotencyConflict,
    PublicationNotFound,
    PublicationPublishRequest,
    PublicationPublishResponse,
    PublicationPublishTransportUnavailable,
    PublicationReconciliationIdempotencyConflict,
    PublicationReconciliationRequest,
    PublicationReconciliationResponse,
    PublicationReconciliationResultResponse,
    PublicationResponse,
    PublicationStateError,
    PublicationStatus,
    PublicationValidationError,
    Response,
    UUID,
    User,
    _raise_workflow_http_error,
    approve_publication,
    build_publication_meta_dry_run,
    create_publication_activation,
    create_publication_confirmation,
    create_publication_draft,
    execute_confirmed_meta_publication_with_transport,
    get_current_user,
    get_db,
    get_publication_or_404,
    get_publication_publish_transport,
    reconcile_publication,
    require_workspace_membership,
    require_workspace_publish,
    require_workspace_publish_activation,
    require_workspace_write,
    router,
    select,
    settings,
    status,
    verify_and_consume_publication_activation_for_execution,
)

@router.post(
    "/drafts",
    response_model=PublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    workspace_id: UUID,
    payload: PublicationDraftCreate,
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

    try:
        publication = (
            await create_publication_draft(
                db,
                workspace_id,
                payload.content_generation_id,
                payload.social_account_id,
                current_user.id,
                payload.idempotency_key,
            )
        )

        await db.commit()
        await db.refresh(publication)

        return publication

    except (
        PublicationIdempotencyConflict,
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        await db.rollback()
        _raise_workflow_http_error(exc)

@router.post(
    "/{publication_id}/approve",
    response_model=PublicationResponse,
)
async def approve_publication_endpoint(
    workspace_id: UUID,
    publication_id: UUID,
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

    try:
        publication = await approve_publication(
            db,
            workspace_id,
            publication_id,
            current_user.id,
        )

        await db.commit()
        await db.refresh(publication)

        return publication

    except (
        PublicationIdempotencyConflict,
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        await db.rollback()
        _raise_workflow_http_error(exc)

@router.post(
    "/{publication_id}/dry-run",
    response_model=PublicationDryRunResponse,
)
async def dry_run_publication_endpoint(
    workspace_id: UUID,
    publication_id: UUID,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    #
    # Dry-run is part of the publishing preparation
    # workflow, therefore read-only/viewer membership
    # is intentionally insufficient.
    #
    await require_workspace_write(
        db,
        current_user,
        workspace_id,
    )

    try:
        result = (
            await build_publication_meta_dry_run(
                db,
                workspace_id,
                publication_id,
            )
        )

        return PublicationDryRunResponse(
            provider=result.provider,
            platform=result.platform,
            action=result.action,
            target_account_id=(
                result.target_account_id
            ),
            endpoint_path=result.endpoint_path,
            content_hash=result.content_hash,
            content_length=result.content_length,
        )

    except (
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        _raise_workflow_http_error(exc)
