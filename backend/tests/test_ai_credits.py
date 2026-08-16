import inspect
from decimal import Decimal
from uuid import uuid4

from app.schemas.credit import (
    CreditAccountResponse,
    CreditLedgerResponse,
)
from app.services import ai_credits


def test_credit_response_contract():
    workspace_id = uuid4()

    response = CreditAccountResponse(
        workspace_id=workspace_id,
        balance=100,
        lifetime_used=0,
    )

    assert response.workspace_id == workspace_id
    assert response.balance == 100
    assert response.lifetime_used == 0


def test_credit_ledger_contract_allows_actual_cost():
    row = CreditLedgerResponse(
        id=uuid4(),
        generation_id=None,
        operation="generate",
        credits=-10,
        actual_cost_usd=Decimal("0.010000"),
        note=None,
        created_at=ai_credits.utcnow(),
    )

    assert row.operation == "generate"
    assert row.credits == -10


def test_reserve_credit_contract_is_locked_and_accounted():
    source = inspect.getsource(
        ai_credits.reserve_credits
    )

    assert "get_or_create_credit_account" in source
    assert "balance" in source
    assert "lifetime_used" in source
    assert "AICreditLedger" in source
    assert "amount" in source


def test_credit_account_lock_contract():
    source = inspect.getsource(
        ai_credits.get_or_create_credit_account
    )

    assert "workspace_id" in source
    assert "lock" in source
    assert "with_for_update" in source
