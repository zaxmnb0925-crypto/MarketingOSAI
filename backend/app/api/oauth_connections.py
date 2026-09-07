import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.workspace_access import require_workspace_write
from app.core.config import settings
from app.core.request_context import get_request_id
from app.core.database import get_db
from app.models.social_account import (
    SocialAccount,
    SocialPlatform,
)
from app.models.subscription import (
    WorkspaceSubscription,
)
from app.models.user import User
from app.schemas.oauth_connection import (
    OAuthCallbackResponse,
    OAuthConnectResponse,
    OAuthDiscoveredPage,
)
from app.services.meta_permissions import (
    MetaGraphPermissionHTTPTransport,
    MetaPermissionNotReadyError,
    MetaPermissionProviderError,
    MetaPermissionValidationError,
    verify_meta_managed_pages_for_publishing,
)
from app.services.meta_oauth import (
    MetaOAuthExchangeError,
    MetaOAuthIdentityError,
    MetaOAuthPageDiscoveryError,
    exchange_code_for_access_token,
    get_meta_managed_pages,
    get_meta_user_identity,
)
from app.services.entitlements import (
    SOCIAL_ACCOUNTS_MAX_KEY,
    EntitlementCapacityExceeded,
    EntitlementUnavailable,
    require_capacity,
)
from app.services.social_account_connection import (
    upsert_meta_page_connections,
)
from app.services.oauth_providers import (
    UnsupportedOAuthProvider,
    build_authorization_url,
    get_oauth_provider,
)
from app.services.oauth_state import (
    OAuthStateError,
    consume_and_verify_oauth_state_v2,
    create_oauth_state_v2,
)


logger = logging.getLogger(__name__)


async def _require_social_asset_capacity(
    db: AsyncSession,
    workspace_id: UUID,
    pages: tuple[MetaManagedPage, ...],
) -> None:
    # Serialize OAuth callbacks for this workspace so two
    # concurrent callbacks cannot consume the same slots.
    lock_result = await db.execute(
        select(WorkspaceSubscription.workspace_id)
        .where(
            WorkspaceSubscription.workspace_id
            == workspace_id
        )
        .with_for_update()
    )

    if lock_result.scalar_one_or_none() is None:
        raise EntitlementUnavailable(
            "Subscription is unavailable"
        )

    existing_result = await db.execute(
        select(
            SocialAccount.platform,
            SocialAccount.platform_account_id,
        )
        .where(
            SocialAccount.workspace_id
            == workspace_id,
            SocialAccount.is_active.is_(True),
            SocialAccount.platform_account_id.is_not(None),
        )
    )

    existing_assets = {
        (
            getattr(platform, "value", str(platform)),
            str(platform_account_id),
        )
        for platform, platform_account_id
        in existing_result.all()
    }

    incoming_assets = {
        (
            SocialPlatform.facebook.value,
            page.id,
        )
        for page in pages
        if page.id
    }

    new_asset_count = len(
        incoming_assets - existing_assets
    )

    if new_asset_count < 1:
        return

    await require_capacity(
        db,
        workspace_id,
        SOCIAL_ACCOUNTS_MAX_KEY,
        len(existing_assets),
        requested=new_asset_count,
    )


router = APIRouter(
    tags=["oauth-connections"],
)


@router.post(
    "/api/workspaces/{workspace_id}/oauth/{provider}/connect",
    response_model=OAuthConnectResponse,
)
async def connect_oauth_provider(
    workspace_id: UUID,
    provider: str,
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
        get_oauth_provider(provider)
    except UnsupportedOAuthProvider as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    state_value = await create_oauth_state_v2(
        workspace_id,
        provider,
        current_user.id,
    )

    authorization_url = build_authorization_url(
        provider,
        state_value,
    )

    return OAuthConnectResponse(
        provider=provider,
        authorization_url=authorization_url,
    )


@router.get(
    "/api/oauth/{provider}/callback",
    response_model=OAuthCallbackResponse,
)
async def oauth_callback(
    provider: str,
    state_value: str = Query(
        alias="state"
    ),
    code: str | None = Query(
        default=None
    ),
    error: str | None = Query(
        default=None
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        get_oauth_provider(provider)
    except UnsupportedOAuthProvider as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    try:
        payload = (
            await consume_and_verify_oauth_state_v2(
                state_value,
                expected_provider=provider,
            )
        )
    except OAuthStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Re-check the initiating user at callback time.
    # OAuth state proves who started the flow, but does
    # not preserve authorization for the full TTL.
    result = await db.execute(
        select(User).where(
            User.id == payload.user_id
        )
    )

    initiating_user = (
        result.scalar_one_or_none()
    )

    if (
        initiating_user is None
        or not initiating_user.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "OAuth initiator is no longer "
                "authorized"
            ),
        )

    await require_workspace_write(
        db,
        initiating_user,
        payload.workspace_id,
    )

    # Consume a valid state even when the user cancelled
    # the provider authorization flow.
    if error is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "OAuth authorization was not completed"
            ),
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "OAuth authorization code is missing"
            ),
        )

    if provider != "meta":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "OAuth token exchange is not implemented "
                "for this provider"
            ),
        )

    try:
        token = await exchange_code_for_access_token(
            code
        )

        await get_meta_user_identity(
            token.access_token
        )

        managed_pages = await get_meta_managed_pages(
            token.access_token
        )

    except MetaOAuthExchangeError as exc:
        logger.warning(
            "meta_oauth_token_exchange_failed "
            "request_id=%s",
            get_request_id(),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Meta OAuth token exchange failed",
        ) from exc

    except MetaOAuthIdentityError as exc:
        logger.warning(
            "Meta OAuth identity verification failed"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Meta OAuth identity verification failed"
            ),
        ) from exc

    except MetaOAuthPageDiscoveryError as exc:
        logger.warning(
            "meta_oauth_page_discovery_failed "
            "request_id=%s",
            get_request_id(),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Meta OAuth Page discovery failed"
            ),
        ) from exc

    if not managed_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No Facebook Pages were authorized"
            ),
        )

    #
    # Verify the actual Page-token permissions before
    # persisting the connection. Business Login config
    # names and Page tasks are not treated as proof of
    # token grants.
    #
    try:
        permission_transport = (
            MetaGraphPermissionHTTPTransport(
                app_id=settings.meta_app_id or "",
                app_secret=(
                    settings.meta_app_secret
                    or ""
                ),
            )
        )

        verified_scopes_by_page_id = (
            await verify_meta_managed_pages_for_publishing(
                tuple(managed_pages),
                permission_transport,
            )
        )

    except MetaPermissionNotReadyError as exc:
        logger.warning(
            "Meta Page publishing permissions "
            "are incomplete"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Facebook Page publishing "
                "permissions are incomplete"
            ),
        ) from exc

    except MetaPermissionValidationError as exc:
        logger.error(
            "Meta permission verification "
            "configuration is invalid"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Meta permission verification "
                "is unavailable"
            ),
        ) from exc

    except MetaPermissionProviderError as exc:
        logger.warning(
            "Meta permission verification "
            "request failed"
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Meta permission verification failed"
            ),
        ) from exc

    try:
        await _require_social_asset_capacity(
            db,
            payload.workspace_id,
            tuple(managed_pages),
        )
    except EntitlementCapacityExceeded as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "目前方案的社群資產綁定數量已達上限；"
                "請先解除既有帳號或升級方案。"
            ),
        ) from exc
    except EntitlementUnavailable as exc:
        await db.rollback()
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "目前無法確認方案的社群資產上限，"
                "請稍後再試。"
            ),
        ) from exc

    try:
        await upsert_meta_page_connections(
            db,
            payload.workspace_id,
            tuple(managed_pages),
            verified_scopes_by_page_id,
        )

        await db.commit()

    except Exception as exc:
        await db.rollback()

        # Never log provider tokens, ciphertext,
        # SQL parameters, or provider responses here.
        logger.error(
            "Social account persistence failed"
        )

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "Social account connection "
                "could not be saved"
            ),
        ) from exc

    safe_pages = [
        OAuthDiscoveredPage(
            id=page.id,
            name=page.name,
            tasks=list(page.tasks),
        )
        for page in managed_pages
    ]

    return OAuthCallbackResponse(
        provider=provider,
        status="pages_connected",
        workspace_id=str(
            payload.workspace_id
        ),
        page_count=len(safe_pages),
        pages=safe_pages,
    )
