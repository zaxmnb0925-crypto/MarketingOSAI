import ast
import importlib.util
import inspect
from pathlib import Path

import pytest

from app.api import content
from app.models.ai_credit import AICreditLedger
from app.services import ai_credits


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / (
    "f0289623eb1e_p4_ai_accounting_transaction_contract.py"
)


def _calls(source, attribute):
    tree = ast.parse(source)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


def test_services_never_own_commit_or_rollback():
    for service in (
        ai_credits.reserve_credits,
        ai_credits.refund_credits,
        ai_credits.record_actual_cost,
    ):
        source = inspect.getsource(service)
        assert not _calls(source, "commit")
        assert not _calls(source, "rollback")


def test_account_and_subscription_locks_are_retained():
    reserve = inspect.getsource(ai_credits.reserve_credits)
    refund = inspect.getsource(ai_credits.refund_credits)
    for source in (reserve, refund):
        assert "lock=True" in source
        assert "get_subscription_locked" in source
    assert "with_for_update" in inspect.getsource(
        ai_credits.get_subscription_locked
    )


def test_model_declares_both_partial_unique_indexes():
    indexes = {index.name: index for index in AICreditLedger.__table__.indexes}
    assert "uq_ai_credit_ledger_generation_debit" in indexes
    assert (
        "uq_ai_credit_ledger_generation_terminal_refund"
        in indexes
    )
    for name in (
        "uq_ai_credit_ledger_generation_debit",
        "uq_ai_credit_ledger_generation_terminal_refund",
    ):
        assert indexes[name].unique
        assert indexes[name].dialect_options["postgresql"]["where"] is not None


def test_migration_is_fail_closed_and_preserves_null_generations():
    source = MIGRATION.read_text()
    assert "down_revision" in source
    assert "e8f3a1c6d2b4" in source
    assert "generation_id IS NOT NULL" in source
    assert "HAVING COUNT(*) > 1" in source
    assert "RuntimeError" in source
    assert "DELETE" not in source.upper()
    assert "UPDATE" not in source.upper()
    assert "uq_ai_credit_ledger_generation_debit" in source
    assert "uq_ai_credit_ledger_generation_terminal_refund" in source


def test_migration_duplicate_detection_blocks_index_creation(
    monkeypatch,
):
    spec = importlib.util.spec_from_file_location(
        "p4_accounting_migration",
        MIGRATION,
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class Result:
        def scalar_one(self):
            return 1

    class Bind:
        def execute(self, statement):
            return Result()

    created = []
    monkeypatch.setattr(migration.op, "get_bind", Bind)
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda *args, **kwargs: created.append(args),
    )

    with pytest.raises(RuntimeError, match="duplicate"):
        migration.upgrade()
    assert created == []


def test_orchestrator_has_atomic_phases_and_external_io_boundary():
    source = inspect.getsource(content.generate_content)
    provider = source.index("await generate_social_content")
    pre_provider_commit = source.rfind("await db.commit()", 0, provider)
    reserve = source.index("await reserve_credits")
    assert reserve < pre_provider_commit < provider
    assert "await db.flush()" in source[:reserve]
    assert "await _lock_pending_generation" in source[provider:]
    assert "ContentGeneration.workspace_id == workspace_id" in (
        inspect.getsource(content._lock_pending_generation)
    )
    assert ".with_for_update()" in inspect.getsource(
        content._lock_pending_generation
    )


def test_terminal_refund_and_failed_state_share_each_commit():
    source = inspect.getsource(content.generate_content)
    for operation in (
        "content_policy_refund",
        "provider_failure_refund",
    ):
        start = source.index(f'operation="{operation}"')
        commit = source.index("await db.commit()", start)
        fragment = source[start:commit]
        assert "ContentStatus.failed" in fragment


def test_p3_customer_serializer_remains_internal_field_free():
    source = inspect.getsource(content.serialize_customer_generation)
    for internal in (
        "prompt",
        "model",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "credit",
    ):
        assert internal not in source
