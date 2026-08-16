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
    "/{publication_id}/reconcile",
    response_model=PublicationReconciliationResultResponse,
)
async def reconcile_publication_endpoint(
    workspace_id: UUID,
    publication_id: UUID,
    payload: PublicationReconciliationRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    #
    # Operator recovery uses the established publishing-role
    # boundary: owner / admin / manager.
    #
    # It intentionally does NOT require:
    # - real publishing kill switches
    # - canary target policy
    # - activation
    # - confirmation
    # - Redis
    # - OAuth credential decryption
    # - provider transport
    #
    await require_workspace_publish(
        db,
        current_user,
        workspace_id,
    )

    try:
        reconciliation, publication = (
            await reconcile_publication(
                db,
                workspace_id=workspace_id,
                publication_id=publication_id,
                operator_user_id=current_user.id,
                decision=payload.decision,
                publish_attempt_number=(
                    payload.publish_attempt_number
                ),
                idempotency_key=(
                    payload.idempotency_key
                ),
                evidence_note=(
                    payload.evidence_note
                ),
                provider_post_id=(
                    payload.provider_post_id
                ),
                provider_permalink=(
                    payload.provider_permalink
                ),
            )
        )

        #
        # Service owns locking/flush only.
        # HTTP boundary owns commit/rollback.
        #
        await db.commit()

        await db.refresh(
            reconciliation
        )

        await db.refresh(
            publication
        )

        return PublicationReconciliationResultResponse(
            reconciliation=(
                PublicationReconciliationResponse.model_validate(
                    reconciliation
                )
            ),
            publication_status=(
                publication.status
            ),
            reconciliation_required=(
                publication.reconciliation_required
            ),
        )

    except PublicationReconciliationIdempotencyConflict as exc:
        await db.rollback()

        #
        # Keep the response deterministic and avoid returning
        # operator evidence or request payload data.
        #
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Reconciliation idempotency conflict"
            ),
        ) from exc

    except (
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        await db.rollback()
        _raise_workflow_http_error(
            exc
        )
