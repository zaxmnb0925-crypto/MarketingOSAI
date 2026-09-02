import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.membership import (
    Membership,
    MembershipRole,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.workspace import Workspace
from app.services.subscriptions import (
    provision_free_subscription,
)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WorkspaceResponse,
)
from app.core.rate_limit import enforce_rate_limit, normalized_login_identifier_hash


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def slugify(value: str) -> str:
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        value.lower(),
    ).strip("-")

    if not slug:
        slug = "workspace"

    return f"{slug}-{uuid.uuid4().hex[:8]}"


async def issue_tokens(
    db: AsyncSession,
    user: User,
    *,
    commit: bool = True,
) -> TokenResponse:

    access_token, expires_in = create_access_token(
        user.id
    )

    raw_refresh, token_digest, expires_at = (
        create_refresh_token()
    )

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest,
            expires_at=expires_at,
        )
    )

    if commit:
        await db.commit()
    else:
        await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=expires_in,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):

    await enforce_rate_limit(
        scope="register",
        identifiers=(
            normalized_login_identifier_hash(
                payload.email
            ),
        ),
        limit=5,
        window_seconds=3600,
    )

    email = normalize_email(
        str(payload.email)
    )

    existing = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=hash_password(
            payload.password
        ),
    )

    workspace = Workspace(
        name=payload.workspace_name.strip(),
        slug=slugify(
            payload.workspace_name
        ),
    )

    db.add_all([
        user,
        workspace,
    ])

    try:
        await db.flush()

        await provision_free_subscription(
            db,
            workspace.id,
        )

        db.add(
            Membership(
                user_id=user.id,
                workspace_id=workspace.id,
                role=MembershipRole.owner,
            )
        )

        tokens = await issue_tokens(
            db,
            user,
            commit=False,
        )

        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    except Exception:
        await db.rollback()
        raise

    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):

    await enforce_rate_limit(
        scope="login",
        identifiers=(
            normalized_login_identifier_hash(
                payload.email
            ),
        ),
        limit=10,
        window_seconds=600,
    )
    email = normalize_email(
        str(payload.email)
    )

    result = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one_or_none()

    if (
        user is None
        or user.password_hash is None
        or not verify_password(
            payload.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return await issue_tokens(
        db,
        user,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):

    digest = hash_refresh_token(
        payload.refresh_token
    )

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest
        ).with_for_update()
    )

    stored = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if (
        stored is None
        or stored.revoked
        or stored.expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_result = await db.execute(
        select(User).where(
            User.id == stored.user_id,
            User.is_active.is_(True),
        )
    )

    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Refresh-token rotation:
    # old token becomes unusable immediately.
    stored.revoked = True

    access_token, expires_in = create_access_token(
        user.id
    )

    raw_refresh, new_digest, expires_at = (
        create_refresh_token()
    )

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_digest,
            expires_at=expires_at,
        )
    )

    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):

    digest = hash_refresh_token(
        payload.refresh_token
    )

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == digest
        )
    )

    stored = result.scalar_one_or_none()

    if stored is not None:
        stored.revoked = True
        await db.commit()

    return None


@router.get(
    "/me",
    response_model=MeResponse,
)
async def me(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(
            Workspace,
            Membership.role,
        )
        .join(
            Membership,
            Membership.workspace_id
            == Workspace.id,
        )
        .where(
            Membership.user_id
            == current_user.id
        )
    )

    rows = result.all()

    return MeResponse(
        user=UserResponse(
            id=current_user.id,
            email=current_user.email,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
        ),
        workspaces=[
            WorkspaceResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                role=role.value,
            )
            for workspace, role in rows
        ],
    )
