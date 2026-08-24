from decimal import Decimal

from pydantic import BaseModel


class UsageGenerationStats(BaseModel):
    total: int
    completed: int
    failed: int
    pending: int
    draft: int


class UsageTokenStats(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class UsageCostStats(BaseModel):
    estimated_cost_usd: Decimal
    average_completed_cost_usd: Decimal


class UsageCreditStats(BaseModel):
    balance: int
    lifetime_used: int
    cycle_granted: int
    cycle_used: int
    cycle_remaining: int
    usage_percent: Decimal


class UsagePlanStats(BaseModel):
    code: str
    name: str
    price_twd: int
    monthly_credits: int
    cycle_start: str
    cycle_end: str
    status: str
    auto_renew: bool


class UsageProfitStats(BaseModel):
    usd_to_twd_rate: Decimal
    ai_cost_twd: Decimal
    plan_revenue_twd: Decimal
    projected_gross_profit_twd: Decimal
    projected_gross_margin_percent: Decimal
    average_completed_cost_twd: Decimal
    cost_per_cycle_credit_twd: Decimal


class WorkspaceUsageResponse(BaseModel):
    workspace_id: str
    generations: UsageGenerationStats
    tokens: UsageTokenStats
    cost: UsageCostStats
    credits: UsageCreditStats
    plan: UsagePlanStats
    profit: UsageProfitStats


class CustomerUsagePlanStats(BaseModel):
    code: str
    name: str
    cycle_start: str
    cycle_end: str
    status: str
    auto_renew: bool


class CustomerWorkspaceUsageResponse(BaseModel):
    workspace_id: str
    generations: UsageGenerationStats
    plan: CustomerUsagePlanStats
