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

@router.get(
    "",
    response_model=list[
        PublicationResponse
    ],
)
async def list_publications(
    workspace_id: UUID,
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

    result = await db.execute(
        select(Publication)
        .where(
            Publication.workspace_id
            == workspace_id
        )
        .order_by(
            Publication.created_at.desc()
        )
    )

    return list(
        result.scalars().all()
    )

@router.get(
    "/{publication_id}",
    response_model=PublicationResponse,
)
async def get_publication(
    workspace_id: UUID,
    publication_id: UUID,
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

    return await get_publication_or_404(
        db,
        workspace_id,
        publication_id,
    )
