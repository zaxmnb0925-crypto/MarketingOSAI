import inspect
from types import SimpleNamespace
from decimal import Decimal
from uuid import uuid4

from app.schemas.credit import (
    CreditAccountResponse,
    CreditLedgerResponse,
)
from app.services import ai_credits
import pytest


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


def test_accounting_services_are_flush_only():
    for service in (
        ai_credits.reserve_credits,
        ai_credits.refund_credits,
        ai_credits.record_actual_cost,
    ):
        source = inspect.getsource(service)
        assert ".commit(" not in source
        assert ".rollback(" not in source

    assert ".flush(" in inspect.getsource(
        ai_credits.reserve_credits
    )
    assert ".flush(" in inspect.getsource(
        ai_credits.refund_credits
    )


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _CostSession:
    def __init__(self, ledger):
        self.ledger = ledger
        self.flush_count = 0

    async def execute(self, statement):
        return _ScalarResult(self.ledger)

    async def flush(self):
        self.flush_count += 1

    def add(self, value):
        self.added = value


@pytest.mark.asyncio
async def test_actual_cost_is_write_once_and_idempotent():
    ledger = SimpleNamespace(actual_cost_usd=None)
    db = _CostSession(ledger)

    await ai_credits.record_actual_cost(
        db,
        uuid4(),
        Decimal("0.125000"),
    )
    assert ledger.actual_cost_usd == Decimal("0.125000")
    assert db.flush_count == 1

    await ai_credits.record_actual_cost(
        db,
        uuid4(),
        Decimal("0.125000"),
    )
    assert db.flush_count == 1

    with pytest.raises(
        ai_credits.AICreditAccountingConflict
    ):
        await ai_credits.record_actual_cost(
            db,
            uuid4(),
            Decimal("0.250000"),
        )


@pytest.mark.asyncio
async def test_exact_debit_replay_does_not_mutate_balance(
    monkeypatch,
):
    account = SimpleNamespace(balance=9, lifetime_used=4)
    subscription = SimpleNamespace(credits_used=4)
    existing = SimpleNamespace(
        operation="content_generation",
        credits=-1,
    )

    async def account_locked(*args, **kwargs):
        return account

    async def subscription_locked(*args, **kwargs):
        return subscription

    async def existing_event(*args, **kwargs):
        return existing

    monkeypatch.setattr(
        ai_credits,
        "get_or_create_credit_account",
        account_locked,
    )
    monkeypatch.setattr(
        ai_credits,
        "get_subscription_locked",
        subscription_locked,
    )
    monkeypatch.setattr(
        ai_credits,
        "_get_existing_generation_accounting_event",
        existing_event,
    )

    db = _CostSession(None)
    returned_account, returned_event = await ai_credits.reserve_credits(
        db,
        uuid4(),
        1,
        generation_id=uuid4(),
    )
    assert returned_account is account
    assert returned_event is existing
    assert account.balance == 9
    assert account.lifetime_used == 4
    assert subscription.credits_used == 4
    assert db.flush_count == 0


@pytest.mark.asyncio
async def test_cross_reason_terminal_refund_fails_closed(
    monkeypatch,
):
    account = SimpleNamespace(balance=9, lifetime_used=4)
    subscription = SimpleNamespace(credits_used=4)
    existing = SimpleNamespace(
        operation="content_policy_refund",
        credits=1,
    )

    async def account_locked(*args, **kwargs):
        return account

    async def subscription_locked(*args, **kwargs):
        return subscription

    async def existing_event(*args, **kwargs):
        return existing

    monkeypatch.setattr(
        ai_credits,
        "get_or_create_credit_account",
        account_locked,
    )
    monkeypatch.setattr(
        ai_credits,
        "get_subscription_locked",
        subscription_locked,
    )
    monkeypatch.setattr(
        ai_credits,
        "_get_existing_generation_accounting_event",
        existing_event,
    )

    with pytest.raises(
        ai_credits.AICreditAccountingConflict
    ):
        await ai_credits.refund_credits(
            _CostSession(None),
            uuid4(),
            1,
            generation_id=uuid4(),
            operation="provider_failure_refund",
        )

    assert account.balance == 9
    assert account.lifetime_used == 4
    assert subscription.credits_used == 4


@pytest.mark.asyncio
async def test_exact_terminal_refund_replay_is_side_effect_free(
    monkeypatch,
):
    account = SimpleNamespace(balance=10, lifetime_used=3)
    subscription = SimpleNamespace(credits_used=3)
    existing = SimpleNamespace(
        operation="provider_failure_refund",
        credits=1,
    )

    async def account_locked(*args, **kwargs):
        return account

    async def subscription_locked(*args, **kwargs):
        return subscription

    async def existing_event(*args, **kwargs):
        return existing

    monkeypatch.setattr(
        ai_credits,
        "get_or_create_credit_account",
        account_locked,
    )
    monkeypatch.setattr(
        ai_credits,
        "get_subscription_locked",
        subscription_locked,
    )
    monkeypatch.setattr(
        ai_credits,
        "_get_existing_generation_accounting_event",
        existing_event,
    )

    db = _CostSession(None)
    returned = await ai_credits.refund_credits(
        db,
        uuid4(),
        1,
        generation_id=uuid4(),
        operation="provider_failure_refund",
    )
    assert returned is account
    assert account.balance == 10
    assert account.lifetime_used == 3
    assert subscription.credits_used == 3
    assert db.flush_count == 0
