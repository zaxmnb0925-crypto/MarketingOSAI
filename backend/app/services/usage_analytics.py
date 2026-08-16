from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_generation import (
    ContentGeneration,
    ContentStatus,
)
from app.services.ai_credits import (
    get_or_create_credit_account,
)
from app.services.subscriptions import (
    ensure_subscription_cycle,
)


ZERO = Decimal("0")

# v0.8C 固定商業分析匯率。
# 後續會改成可設定或匯率服務。
USD_TO_TWD_RATE = Decimal("32.00")


def q6(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.000001"),
        rounding=ROUND_HALF_UP,
    )


def q2(value: Decimal) -> Decimal:
    return value.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


async def get_workspace_usage(
    db: AsyncSession,
    workspace_id: UUID,
) -> dict:

    account = await get_or_create_credit_account(
        db,
        workspace_id,
    )

    subscription, plan = (
        await ensure_subscription_cycle(
            db,
            workspace_id,
            account,
        )
    )

    await db.flush()

    generation_query = select(
        func.count(
            ContentGeneration.id
        ).label("total"),

        func.sum(
            case(
                (
                    ContentGeneration.status
                    == ContentStatus.completed,
                    1,
                ),
                else_=0,
            )
        ).label("completed"),

        func.sum(
            case(
                (
                    ContentGeneration.status
                    == ContentStatus.failed,
                    1,
                ),
                else_=0,
            )
        ).label("failed"),

        func.sum(
            case(
                (
                    ContentGeneration.status
                    == ContentStatus.pending,
                    1,
                ),
                else_=0,
            )
        ).label("pending"),

        func.sum(
            case(
                (
                    ContentGeneration.status
                    == ContentStatus.draft,
                    1,
                ),
                else_=0,
            )
        ).label("draft"),

        func.coalesce(
            func.sum(
                ContentGeneration.input_tokens
            ),
            0,
        ).label("input_tokens"),

        func.coalesce(
            func.sum(
                ContentGeneration.output_tokens
            ),
            0,
        ).label("output_tokens"),

        func.coalesce(
            func.sum(
                ContentGeneration.estimated_cost_usd
            ),
            0,
        ).label("estimated_cost_usd"),
    ).where(
        ContentGeneration.workspace_id
        == workspace_id
    )

    result = await db.execute(
        generation_query
    )

    stats = result.one()

    completed = int(
        stats.completed or 0
    )

    total_cost_usd = Decimal(
        stats.estimated_cost_usd or 0
    )

    average_cost_usd = (
        total_cost_usd
        / Decimal(completed)
        if completed > 0
        else ZERO
    )

    cycle_used = int(
        subscription.credits_used or 0
    )

    cycle_granted = int(
        subscription.credits_granted or 0
    )

    cycle_remaining = max(
        cycle_granted - cycle_used,
        0,
    )

    usage_percent = (
        (
            Decimal(cycle_used)
            / Decimal(cycle_granted)
            * Decimal("100")
        )
        if cycle_granted > 0
        else ZERO
    )

    input_tokens = int(
        stats.input_tokens or 0
    )

    output_tokens = int(
        stats.output_tokens or 0
    )

    ai_cost_twd = (
        total_cost_usd
        * USD_TO_TWD_RATE
    )

    plan_revenue_twd = Decimal(
        plan.price_twd
    )

    projected_gross_profit_twd = (
        plan_revenue_twd
        - ai_cost_twd
    )

    projected_gross_margin_percent = (
        (
            projected_gross_profit_twd
            / plan_revenue_twd
            * Decimal("100")
        )
        if plan_revenue_twd > 0
        else ZERO
    )

    average_completed_cost_twd = (
        average_cost_usd
        * USD_TO_TWD_RATE
    )

    cost_per_cycle_credit_twd = (
        (
            ai_cost_twd
            / Decimal(cycle_used)
        )
        if cycle_used > 0
        else ZERO
    )

    return {
        "workspace_id": str(
            workspace_id
        ),

        "generations": {
            "total": int(
                stats.total or 0
            ),
            "completed": completed,
            "failed": int(
                stats.failed or 0
            ),
            "pending": int(
                stats.pending or 0
            ),
            "draft": int(
                stats.draft or 0
            ),
        },

        "tokens": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": (
                input_tokens
                + output_tokens
            ),
        },

        "cost": {
            "estimated_cost_usd": (
                q6(total_cost_usd)
            ),
            "average_completed_cost_usd": (
                q6(average_cost_usd)
            ),
        },

        "credits": {
            "balance": int(
                account.balance
            ),
            "lifetime_used": int(
                account.lifetime_used
            ),
            "cycle_granted": (
                cycle_granted
            ),
            "cycle_used": cycle_used,
            "cycle_remaining": (
                cycle_remaining
            ),
            "usage_percent": (
                q2(usage_percent)
            ),
        },

        "plan": {
            "code": (
                subscription.plan_code
            ),
            "name": plan.name,
            "price_twd": (
                plan.price_twd
            ),
            "monthly_credits": (
                plan.monthly_credits
            ),
            "cycle_start": (
                subscription
                .cycle_start
                .isoformat()
            ),
            "cycle_end": (
                subscription
                .cycle_end
                .isoformat()
            ),
            "status": (
                subscription.status
            ),
            "auto_renew": (
                subscription.auto_renew
            ),
        },

        "profit": {
            "usd_to_twd_rate": (
                USD_TO_TWD_RATE
            ),
            "ai_cost_twd": (
                q2(ai_cost_twd)
            ),
            "plan_revenue_twd": (
                q2(plan_revenue_twd)
            ),
            "projected_gross_profit_twd": (
                q2(
                    projected_gross_profit_twd
                )
            ),
            "projected_gross_margin_percent": (
                q2(
                    projected_gross_margin_percent
                )
            ),
            "average_completed_cost_twd": (
                q2(
                    average_completed_cost_twd
                )
            ),
            "cost_per_cycle_credit_twd": (
                q6(
                    cost_per_cycle_credit_twd
                )
            ),
        },
    }
