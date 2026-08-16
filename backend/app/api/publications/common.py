from app.services.publication_activation_execution import (
    ControlledPublicationActivationRejected,
    verify_and_consume_publication_activation_for_execution,
)
from app.api.publication_activation_access import (
    require_workspace_publish_activation,
)
from app.schemas.publication import (
    PublicationActivationResponse,
)
from app.services.publication_activation import (
    PUBLICATION_ACTIVATION_TTL_SECONDS,
    create_publication_activation,
)
from uuid import UUID
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.api.workspace_access import (
    require_workspace_membership,
    require_workspace_publish,
    require_workspace_write,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.publication import (
    Publication,
    PublicationStatus,
)
from app.models.user import User
from app.schemas.publication import (
    PublicationConfirmationResponse,
    PublicationDraftCreate,
    PublicationDryRunResponse,
    PublicationPublishRequest,
    PublicationPublishResponse,
    PublicationReconciliationRequest,
    PublicationReconciliationResponse,
    PublicationReconciliationResultResponse,
    PublicationResponse,
)
from app.services.publication_dry_run import (
    build_publication_meta_dry_run,
)
from app.services.publication_confirmation import (
    PUBLICATION_CONFIRMATION_TTL_SECONDS,
    create_publication_confirmation,
)
from app.services.publication_controlled_execution import (
    ControlledPublicationConfirmationRejected,
    ControlledPublicationContentHashMismatch,
    ControlledPublicationExecutionDisabled,
    execute_confirmed_meta_publication_with_transport,
)
from app.services.publication_executor import (
    PublicationExecutionError,
    PublicationExecutionOutcomeUnknown,
    PublicationExecutionProviderRejected,
)
from app.services.publication_publish_transport import (
    PublicationPublishTransportUnavailable,
    get_publication_publish_transport,
)
from app.services.publication_reconciliation import (
    PublicationReconciliationIdempotencyConflict,
    reconcile_publication,
)
from app.services.publication_workflow import (
    PublicationIdempotencyConflict,
    PublicationNotFound,
    PublicationStateError,
    PublicationValidationError,
    approve_publication,
    create_publication_draft,
)
router = APIRouter(
    prefix=(
        "/api/workspaces/{workspace_id}"
        "/publications"
    ),
    tags=["Publications"],
)
def _raise_workflow_http_error(
    exc: Exception,
) -> None:
    if isinstance(
        exc,
        PublicationIdempotencyConflict,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        PublicationNotFound,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication not found",
        ) from exc

    if isinstance(
        exc,
        PublicationValidationError,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        PublicationStateError,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    raise exc
async def get_publication_or_404(
    db: AsyncSession,
    workspace_id: UUID,
    publication_id: UUID,
) -> Publication:
    result = await db.execute(
        select(Publication).where(
            Publication.id == publication_id,
            Publication.workspace_id
            == workspace_id,
        )
    )

    publication = (
        result.scalar_one_or_none()
    )

    if publication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication not found",
        )

    return publication
