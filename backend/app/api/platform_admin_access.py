from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.commercial import (
    PlatformAdminMembership,
    PlatformAdminRole,
)
from app.models.user import User


PLATFORM_ADMIN_READ_ROLES = {
    PlatformAdminRole.support.value,
    PlatformAdminRole.billing_admin.value,
    PlatformAdminRole.subscription_admin.value,
    PlatformAdminRole.super_admin.value,
}

PLATFORM_ADMIN_ACCOUNTING_READ_ROLES = {
    PlatformAdminRole.support.value,
    PlatformAdminRole.billing_admin.value,
    PlatformAdminRole.super_admin.value,
}

PLATFORM_ADMIN_PAYMENT_READ_ROLES = {
    PlatformAdminRole.support.value,
    PlatformAdminRole.billing_admin.value,
    PlatformAdminRole.super_admin.value,
}

PLATFORM_ADMIN_SUBSCRIPTION_READ_ROLES = {
    PlatformAdminRole.support.value,
    PlatformAdminRole.subscription_admin.value,
    PlatformAdminRole.super_admin.value,
}

PLATFORM_ADMIN_PAYMENT_ROLES = {
    PlatformAdminRole.billing_admin.value,
    PlatformAdminRole.super_admin.value,
}

PLATFORM_ADMIN_SUBSCRIPTION_ROLES = {
    PlatformAdminRole.subscription_admin.value,
    PlatformAdminRole.super_admin.value,
}

PLATFORM_ADMIN_OVERRIDE_ROLES = {
    PlatformAdminRole.super_admin.value,
}


async def require_platform_admin_roles(
    db: AsyncSession,
    user: User,
    allowed_roles: Iterable[str],
) -> PlatformAdminMembership:
    result = await db.execute(
        select(
            PlatformAdminMembership
        ).where(
            PlatformAdminMembership.user_id
            == user.id,
            PlatformAdminMembership.is_active.is_(
                True
            ),
            PlatformAdminMembership.revoked_at.is_(
                None
            ),
        )
    )

    membership = (
        result.scalar_one_or_none()
    )

    if (
        membership is None
        or membership.role
        not in set(allowed_roles)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Platform administrator "
                "permission required"
            ),
        )

    return membership


async def require_platform_admin_read(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db,
        current_user,
        PLATFORM_ADMIN_READ_ROLES,
    )


async def require_platform_admin_accounting_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db, current_user, PLATFORM_ADMIN_ACCOUNTING_READ_ROLES
    )


async def require_platform_admin_payment_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db, current_user, PLATFORM_ADMIN_PAYMENT_READ_ROLES
    )


async def require_platform_admin_subscription_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db, current_user, PLATFORM_ADMIN_SUBSCRIPTION_READ_ROLES
    )


async def require_platform_admin_payment(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db,
        current_user,
        PLATFORM_ADMIN_PAYMENT_ROLES,
    )


async def require_platform_admin_subscription(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db,
        current_user,
        PLATFORM_ADMIN_SUBSCRIPTION_ROLES,
    )


async def require_platform_admin_override(
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> PlatformAdminMembership:
    return await require_platform_admin_roles(
        db,
        current_user,
        PLATFORM_ADMIN_OVERRIDE_ROLES,
    )
