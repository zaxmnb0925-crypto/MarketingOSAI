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
from app.core.rate_limit import enforce_rate_limit

@router.post(
    "/{publication_id}/publish-confirmation",
    response_model=PublicationConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_publish_confirmation_endpoint(
    workspace_id: UUID,
    publication_id: UUID,
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    #
    # External publishing has a narrower authorization
    # boundary than ordinary Workspace writes.
    #
    await require_workspace_publish(
        db,
        current_user,
        workspace_id,
    )

    #
    # Reuse the existing read-only publishing preflight.
    # This validates approval, immutable content integrity,
    # exact target/account state, platform compatibility
    # and credential presence without decrypting it.
    #
    try:
        dry_run = (
            await build_publication_meta_dry_run(
                db,
                workspace_id,
                publication_id,
            )
        )
    except (
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        _raise_workflow_http_error(
            exc
        )

    #
    # Confirmation creation changes Redis only.
    # It must never transition the Publication, increment
    # attempts, decrypt an OAuth credential or call Meta.
    #
    try:
        confirmation_value = (
            await create_publication_confirmation(
                workspace_id=workspace_id,
                publication_id=publication_id,
                user_id=current_user.id,
                content_hash=dry_run.content_hash,
            )
        )
    except Exception:
        #
        # Fail closed and do not expose Redis/runtime
        # details to the client.
        #
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Publication confirmation "
                "could not be created"
            ),
        ) from None

    #
    # The response contains an opaque one-time bearer
    # confirmation and must never be stored by browsers,
    # proxies or intermediary caches.
    #
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return PublicationConfirmationResponse(
        publication_id=publication_id,
        confirmation=confirmation_value,
        expires_in=(
            PUBLICATION_CONFIRMATION_TTL_SECONDS
        ),
        content_hash=dry_run.content_hash,
    )

@router.post(
    "/{publication_id}/publish",
    response_model=PublicationPublishResponse,
)
async def publish_publication_endpoint(
    workspace_id: UUID,
    publication_id: UUID,
    payload: PublicationPublishRequest,
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):
    #
    # Authorization occurs before revealing whether real
    # provider execution is enabled.
    #
    await enforce_rate_limit(
        scope="publish",
        identifiers=(
            str(current_user.id),
            str(workspace_id),
        ),
        limit=5,
        window_seconds=60,
    )
    await require_workspace_publish(
        db,
        current_user,
        workspace_id,
    )

    #
    # Defense in depth:
    # controlled execution checks this again. The endpoint
    # checks it here so transport wiring is never even
    # requested while publishing is disabled.
    #
    if not settings.real_publish_enabled:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Real publishing is disabled",
        )

    #
    # Exact server-side canary target is checked before
    # provider transport construction.
    #
    from app.services.publication_publish_target_policy import (
        PublicationPublishTargetRejected,
        require_allowed_publication_publish_target,
    )

    try:
        require_allowed_publication_publish_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )
    except PublicationPublishTargetRejected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Publication canary target "
                "is unavailable"
            ),
        ) from None

    #
    # At v0.13E-D-A this provider is intentionally
    # fail-closed. Source tests inject a mock implementation.
    #
    try:
        transport = (
            get_publication_publish_transport()
        )
    except PublicationPublishTransportUnavailable:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Real publishing transport "
                "is not configured"
            ),
        ) from None

    #
    # THIRD GATE — exact one-publication activation.
    #
    # Provider wiring has already succeeded, but no credential
    # has been decrypted and no provider request has occurred.
    #
    # Activation is consumed before the existing publication
    # confirmation. Failure therefore cannot reach the durable
    # publishing claim.
    #
    try:
        await verify_and_consume_publication_activation_for_execution(
            db=db,
            workspace_id=workspace_id,
            publication_id=publication_id,
            user_id=current_user.id,
            activation_value=(
                payload.activation
            ),
            expected_content_hash=(
                payload.content_hash
            ),
        )

    except ControlledPublicationExecutionDisabled:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Real publishing is disabled",
        ) from None

    except ControlledPublicationContentHashMismatch:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Publication content hash "
                "no longer matches"
            ),
        ) from None

    except ControlledPublicationActivationRejected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Publication activation is invalid "
                "or no longer available"
            ),
        ) from None

    try:
        result = (
            await execute_confirmed_meta_publication_with_transport(
                db=db,
                workspace_id=workspace_id,
                publication_id=publication_id,
                user_id=current_user.id,
                confirmation_value=(
                    payload.confirmation
                ),
                expected_content_hash=(
                    payload.content_hash
                ),
                transport=transport,
            )
        )

    except ControlledPublicationExecutionDisabled:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Real publishing is disabled",
        ) from None

    except ControlledPublicationContentHashMismatch:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Publication content hash "
                "no longer matches"
            ),
        ) from None

    except ControlledPublicationConfirmationRejected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Publication confirmation is invalid "
                "or no longer available"
            ),
        ) from None

    except PublicationExecutionProviderRejected:
        #
        # Do not expose raw provider data.
        #
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Publishing provider rejected "
                "the request"
            ),
        ) from None

    except PublicationExecutionOutcomeUnknown:
        #
        # The provider may have performed the side effect.
        # Never instruct the client to retry. Return an
        # explicit reconciliation state.
        #
        response.status_code = (
            status.HTTP_202_ACCEPTED
        )

        return PublicationPublishResponse(
            publication_id=publication_id,
            status=PublicationStatus.publishing,
            provider_post_id=None,
            provider_permalink=None,
            reconciliation_required=True,
        )

    except (
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        _raise_workflow_http_error(
            exc
        )

    except PublicationExecutionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Publication execution failed",
        ) from None

    return PublicationPublishResponse(
        publication_id=publication_id,
        status=PublicationStatus.published,
        provider_post_id=(
            result.provider_post_id
        ),
        provider_permalink=(
            result.provider_permalink
        ),
        reconciliation_required=False,
    )

@router.post(
    "/{publication_id}/publish-activation",
    response_model=PublicationActivationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_publication_activation_endpoint(
    workspace_id: UUID,
    publication_id: UUID,
    response: Response,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(
        get_db
    ),
):
    #
    # Activation is intentionally stricter than ordinary
    # publish permission. During this safety phase, only a
    # workspace owner may receive an activation bearer.
    #
    #
    # CANARY mode preserves owner-only activation.
    # NORMAL mode uses the established publish-role policy.
    #
    if settings.meta_publish_canary_mode_enabled:
        await require_workspace_publish_activation(
            db,
            current_user,
            workspace_id,
        )
    else:
        await require_workspace_publish(
            db,
            current_user,
            workspace_id,
        )

    #
    # Exact server-side first-live-post target.
    #
    # Owner authorization alone is not sufficient.
    #
    from app.services.publication_publish_target_policy import (
        PublicationPublishTargetRejected,
        require_allowed_publication_publish_target,
    )

    try:
        require_allowed_publication_publish_target(
            workspace_id=workspace_id,
            publication_id=publication_id,
        )
    except PublicationPublishTargetRejected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Publication canary target "
                "is unavailable"
            ),
        ) from None

    #
    # Bind activation to the exact currently-approved
    # Publication snapshot.
    #
    try:
        dry_run = await build_publication_meta_dry_run(
            db,
            workspace_id,
            publication_id,
        )
    except (
        PublicationValidationError,
        PublicationStateError,
        PublicationNotFound,
    ) as exc:
        _raise_workflow_http_error(
            exc
        )

    try:
        activation_value = (
            await create_publication_activation(
                workspace_id=workspace_id,
                publication_id=publication_id,
                user_id=current_user.id,
                content_hash=(
                    dry_run.content_hash
                ),
            )
        )
    except Exception:
        #
        # Do not expose Redis/backend internals.
        #
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Publication activation "
                "is temporarily unavailable"
            ),
        ) from None

    #
    # The response contains an opaque bearer and must never
    # be stored by intermediary/browser caches.
    #
    response.headers[
        "Cache-Control"
    ] = "no-store"

    response.headers[
        "Pragma"
    ] = "no-cache"

    response.headers[
        "Expires"
    ] = "0"

    return PublicationActivationResponse(
        publication_id=publication_id,
        activation=activation_value,
        expires_in=(
            PUBLICATION_ACTIVATION_TTL_SECONDS
        ),
        content_hash=(
            dry_run.content_hash
        ),
    )
