from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import (
    PlanEntitlement,
    SubscriptionStatus,
    WorkspaceSubscription,
)


SOCIAL_ACCOUNTS_MAX_KEY = "social_accounts.max"

UNLIMITED_FAIR_USE = None


class EntitlementError(RuntimeError):
    pass


class EntitlementUnavailable(EntitlementError):
    pass


class EntitlementCapacityExceeded(
    EntitlementError
):
    pass


@dataclass(frozen=True)
class EffectiveEntitlements:
    workspace_id: UUID
    plan_code: str
    entitlement_version: int
    values: dict[str, Any]

    def get_required(
        self,
        key: str,
    ) -> Any:
        if key not in self.values:
            raise EntitlementUnavailable(
                "Entitlement is unavailable"
            )

        return self.values[key]


async def _load_plan_entitlements(
    db: AsyncSession,
    plan_code: str,
) -> dict[str, Any]:
    result = await db.execute(
        select(PlanEntitlement).where(
            PlanEntitlement.plan_code
            == plan_code
        )
    )

    return {
        row.key: row.value_json
        for row in result.scalars().all()
    }


async def resolve_effective_entitlements(
    db: AsyncSession,
    workspace_id: UUID,
) -> EffectiveEntitlements:
    result = await db.execute(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id
            == workspace_id
        )
    )

    subscription = (
        result.scalar_one_or_none()
    )

    if subscription is None:
        raise EntitlementUnavailable(
            "Subscription is unavailable"
        )

    if (
        subscription.status
        != SubscriptionStatus.active.value
    ):
        raise EntitlementUnavailable(
            "Subscription is not active"
        )

    plan_code = subscription.plan_code
    version = (
        subscription.entitlement_version
    )

    values = await _load_plan_entitlements(
        db,
        plan_code,
    )

    return EffectiveEntitlements(
        workspace_id=workspace_id,
        plan_code=plan_code,
        entitlement_version=version,
        values=values,
    )


async def get_effective_entitlements(
    db: AsyncSession,
    workspace_id: UUID,
) -> EffectiveEntitlements:
    return await resolve_effective_entitlements(
        db,
        workspace_id,
    )


async def require_enabled(
    db: AsyncSession,
    workspace_id: UUID,
    key: str,
) -> None:
    effective = (
        await resolve_effective_entitlements(
            db,
            workspace_id,
        )
    )

    value = effective.get_required(key)

    if value is not True:
        raise EntitlementUnavailable(
            "Entitlement is not enabled"
        )


async def require_capacity(
    db: AsyncSession,
    workspace_id: UUID,
    key: str,
    current_count: int,
    *,
    requested: int = 1,
) -> None:
    if current_count < 0 or requested < 1:
        raise ValueError(
            "Capacity inputs are invalid"
        )

    effective = (
        await resolve_effective_entitlements(
            db,
            workspace_id,
        )
    )

    capacity = effective.get_required(key)

    #
    # JSON null has one explicit meaning for allowance
    # entitlements: no ordinary customer quota; usage is
    # governed by fair-use and operational controls.
    #
    if capacity is UNLIMITED_FAIR_USE:
        return

    if (
        isinstance(capacity, bool)
        or not isinstance(capacity, int)
        or capacity < 0
    ):
        raise EntitlementUnavailable(
            "Entitlement capacity is invalid"
        )

    if current_count + requested > capacity:
        raise EntitlementCapacityExceeded(
            "Entitlement capacity exceeded"
        )
