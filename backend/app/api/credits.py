from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.platform_admin_access import (
    require_platform_admin_accounting_read,
)
from app.core.database import get_db
from app.models.ai_credit import AICreditLedger
from app.models.commercial import PlatformAdminMembership
from app.schemas.credit import (
    CreditAccountResponse,
    CreditLedgerResponse,
)
from app.services.ai_credits import (
    get_or_create_credit_account,
)


router = APIRouter(
    prefix="/api/platform-admin/workspaces/{workspace_id}/ai-credits",
    tags=["Platform AI Accounting"],
)


@router.get(
    "",
    response_model=CreditAccountResponse,
)
async def get_credit_account(
    workspace_id: UUID,
    admin: PlatformAdminMembership = Depends(
        require_platform_admin_accounting_read
    ),
    db: AsyncSession = Depends(get_db),
):


    account = await get_or_create_credit_account(
        db,
        workspace_id,
    )

    await db.commit()

    return CreditAccountResponse(
        workspace_id=account.workspace_id,
        balance=account.balance,
        lifetime_used=account.lifetime_used,
    )


@router.get(
    "/ledger",
    response_model=list[CreditLedgerResponse],
)
async def get_credit_ledger(
    workspace_id: UUID,
    admin: PlatformAdminMembership = Depends(
        require_platform_admin_accounting_read
    ),
    db: AsyncSession = Depends(get_db),
):


    result = await db.execute(
        select(AICreditLedger)
        .where(
            AICreditLedger.workspace_id
            == workspace_id
        )
        .order_by(
            AICreditLedger.created_at.desc()
        )
        .limit(100)
    )

    rows = result.scalars().all()

    return [
        CreditLedgerResponse(
            id=row.id,
            generation_id=row.generation_id,
            operation=row.operation,
            credits=row.credits,
            actual_cost_usd=row.actual_cost_usd,
            note=row.note,
            created_at=row.created_at,
        )
        for row in rows
    ]
