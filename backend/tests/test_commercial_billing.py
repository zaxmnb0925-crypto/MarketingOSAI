import copy
import importlib.util
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import platform_admin_access, platform_admin_billing
from app.models.commercial import (
    AdminSubscriptionAudit,
    PaymentRecord,
    PaymentStatus,
    PlatformAdminRole,
)
from app.models.subscription import WorkspaceSubscription
from sqlalchemy.sql.dml import Insert
from sqlalchemy.sql.selectable import Select
from app.schemas.commercial import (
    ManualPaymentCreateRequest,
    PaymentConfirmationRequest,
)
from app.services import commercial_billing as billing


def moment(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


class FakeScalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class FakeResult:
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = values

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        if self.value is None:
            raise AssertionError("Expected one result")
        return self.value

    def scalars(self):
        return FakeScalars(self.values or [])


class QueueDB:
    def __init__(self, *results):
        self.results = list(results)
        self.added = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        if not self.results:
            raise AssertionError(f"Unexpected statement: {statement}")
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class StatefulResult:
    def __init__(self, rows):
        self.rows = list(rows)

    def scalar_one_or_none(self):
        if not self.rows:
            return None
        if len(self.rows) != 1:
            raise AssertionError(
                f"Expected at most one row, found {len(self.rows)}"
            )
        return self.rows[0]

    def scalar_one(self):
        if len(self.rows) != 1:
            raise AssertionError(
                f"Expected exactly one row, found {len(self.rows)}"
            )
        return self.rows[0]

    def scalars(self):
        return FakeScalars(self.rows)


class StatefulCommercialUoW:
    # Small transactional store driven by production SQL statements.

    def __init__(
        self,
        *,
        payments=(),
        subscriptions=(),
        fail_on_flush=False,
    ):
        initial = {
            "payments": {
                item.id: copy.deepcopy(item)
                for item in payments
            },
            "subscriptions": {
                item.workspace_id: copy.deepcopy(item)
                for item in subscriptions
            },
            "audits": [],
        }
        self._committed = copy.deepcopy(initial)
        self._working = copy.deepcopy(initial)
        self.fail_on_flush = fail_on_flush
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0
        self.failed_flush_state = None

    @staticmethod
    def _filters(statement):
        values = {}
        for criterion in statement._where_criteria:
            name = getattr(
                getattr(criterion, "left", None),
                "name",
                None,
            )
            right = getattr(criterion, "right", None)
            if name is not None and hasattr(right, "value"):
                values[name] = right.value
        return values

    @staticmethod
    def _insert_values(statement):
        return {
            getattr(column, "name", str(column)): getattr(
                value,
                "value",
                value,
            )
            for column, value in statement._values.items()
        }

    @staticmethod
    def _matches(item, filters):
        return all(
            getattr(item, name) == value
            for name, value in filters.items()
        )

    async def execute(self, statement):
        if isinstance(statement, Insert):
            if statement.table.name != "payment_records":
                raise AssertionError(
                    f"Unexpected insert table: {statement.table.name}"
                )
            values = self._insert_values(statement)
            scoped_identity = (
                values["workspace_id"],
                values["idempotency_key"],
            )
            existing = next(
                (
                    item
                    for item in self._working["payments"].values()
                    if (
                        item.workspace_id,
                        item.idempotency_key,
                    ) == scoped_identity
                ),
                None,
            )
            if existing is None:
                created = SimpleNamespace(**values)
                self._working["payments"][created.id] = created
            return StatefulResult([])

        if not isinstance(statement, Select):
            raise AssertionError(
                f"Unexpected SQL statement: {statement}"
            )
        entity = statement.column_descriptions[0].get("entity")
        filters = self._filters(statement)
        if entity is PaymentRecord:
            rows = self._working["payments"].values()
        elif entity is WorkspaceSubscription:
            rows = self._working["subscriptions"].values()
        elif entity is AdminSubscriptionAudit:
            rows = self._working["audits"]
        else:
            raise AssertionError(f"Unexpected selected entity: {entity}")
        return StatefulResult(
            item
            for item in rows
            if self._matches(item, filters)
        )

    def add(self, value):
        if not isinstance(value, AdminSubscriptionAudit):
            raise AssertionError(f"Unexpected added entity: {value}")
        self._working["audits"].append(value)

    async def flush(self):
        self.flushes += 1
        if self.fail_on_flush:
            self.failed_flush_state = copy.deepcopy(self._working)
            raise RuntimeError("injected failure before commit")

    async def commit(self):
        self.commits += 1
        self._committed = copy.deepcopy(self._working)

    async def rollback(self):
        self.rollbacks += 1
        self._working = copy.deepcopy(self._committed)

    def reload_payment(self, payment_id):
        return copy.deepcopy(
            self._working["payments"][payment_id]
        )

    def reload_subscription(self, workspace_id):
        return copy.deepcopy(
            self._working["subscriptions"][workspace_id]
        )

    def payment_rows(self):
        return [
            copy.deepcopy(item)
            for item in self._working["payments"].values()
        ]

    def audit_rows(self):
        return [
            copy.deepcopy(item)
            for item in self._working["audits"]
        ]


def plan(code, list_price, promotion=None):
    return SimpleNamespace(
        code=code,
        is_active=True,
        is_public=True,
        currency="TWD",
        list_price_minor=list_price,
        promotional_price_minor=promotion,
    )


def subscription(
    *,
    plan_code="free",
    status="active",
    starts_at=None,
    expires_at=None,
    renewal_price_minor=0,
    pricing_source="free",
    version=1,
):
    start = starts_at or moment(2026, 8, 2)
    return SimpleNamespace(
        workspace_id=uuid4(),
        plan_code=plan_code,
        status=status,
        starts_at=start,
        expires_at=expires_at,
        activated_at=start,
        activated_by_user_id=None,
        suspended_at=None,
        cancelled_at=None,
        cancellation_effective_at=None,
        renewal_price_minor=renewal_price_minor,
        billing_currency="TWD",
        pricing_source=pricing_source,
        entitlement_version=version,
        updated_at=start,
    )


def payment(workspace_id, amount, *, key="key-1"):
    when = moment(2026, 8, 25)
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        source="manual",
        method="bank_transfer",
        amount_minor=amount,
        currency="TWD",
        status=PaymentStatus.pending.value,
        received_at=when,
        confirmed_at=None,
        confirmed_by_admin_user_id=None,
        external_reference="bank-1",
        customer_note=None,
        internal_note=None,
        idempotency_key=key,
        created_at=when,
        updated_at=when,
    )


def composition_for(sub, segments):
    return billing._composition(
        version=sub.entitlement_version,
        segments=[
            billing._segment(
                start=start,
                end=end,
                plan_code=sub.plan_code,
                price_minor=price,
                currency="TWD",
                payment_record_id=payment_id,
            )
            for start, end, price, payment_id in segments
        ],
    )


def configure_confirmation(monkeypatch, sub, target, before):
    async def locked(db, workspace_id):
        assert workspace_id == sub.workspace_id
        return sub

    async def selectable(db, plan_code):
        assert plan_code == target.code
        return target

    async def load(db, current):
        assert current is sub
        return before

    monkeypatch.setattr(billing, "_locked_subscription", locked)
    monkeypatch.setattr(billing, "_selectable_plan", selectable)
    monkeypatch.setattr(billing, "load_authoritative_composition", load)


async def confirm(
    monkeypatch,
    sub,
    record,
    target,
    before,
    *,
    now,
    price_selection="list",
):
    configure_confirmation(monkeypatch, sub, target, before)
    db = QueueDB(FakeResult(record))
    result = await billing.confirm_manual_payment(
        db,
        workspace_id=sub.workspace_id,
        payment_id=record.id,
        target_plan_code=target.code,
        price_selection=price_selection,
        actor_user_id=uuid4(),
        actor_admin_role="billing_admin",
        reason="customer payment verified",
        request_id="request-1",
        now=now,
    )
    return db, result


def test_received_at_requires_timezone_and_normalizes_equivalent_instants():
    with pytest.raises(ValidationError):
        ManualPaymentCreateRequest(
            method="bank",
            amount_minor=99000,
            received_at="2026-08-24T10:00:00",
            idempotency_key="one",
        )
    utc = ManualPaymentCreateRequest(
        method="bank",
        amount_minor=99000,
        received_at="2026-08-24T02:00:00Z",
        idempotency_key="one",
    )
    offset = ManualPaymentCreateRequest(
        method="bank",
        amount_minor=99000,
        received_at="2026-08-24T10:00:00+08:00",
        idempotency_key="one",
    )
    assert utc.received_at == offset.received_at
    assert utc.received_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_payment_create_reuses_same_material_and_conflicts_on_changes(
    monkeypatch,
):
    workspace_id = uuid4()
    existing = payment(workspace_id, 99000)

    async def locked(db, value):
        assert value == workspace_id
        return object()

    monkeypatch.setattr(billing, "_locked_subscription", locked)
    db = QueueDB(FakeResult(None), FakeResult(existing))
    reused = await billing.create_manual_payment(
        db,
        workspace_id=workspace_id,
        method=existing.method,
        amount_minor=existing.amount_minor,
        currency=existing.currency,
        received_at=existing.received_at,
        external_reference=existing.external_reference,
        customer_note=None,
        internal_note=None,
        idempotency_key=existing.idempotency_key,
    )
    assert reused is existing
    assert db.flushes == 1

    for changed_method, changed_amount in (
        ("cash", existing.amount_minor),
        (existing.method, existing.amount_minor + 1),
    ):
        db = QueueDB(FakeResult(None), FakeResult(existing))
        with pytest.raises(billing.CommercialConflict):
            await billing.create_manual_payment(
                db,
                workspace_id=workspace_id,
                method=changed_method,
                amount_minor=changed_amount,
                currency=existing.currency,
                received_at=existing.received_at,
                external_reference=existing.external_reference,
                customer_note=None,
                internal_note=None,
                idempotency_key=existing.idempotency_key,
            )
    with pytest.raises(billing.CommercialValidationError):
        await billing.create_manual_payment(
            QueueDB(),
            workspace_id=workspace_id,
            method=existing.method,
            amount_minor=existing.amount_minor,
            currency="USD",
            received_at=existing.received_at,
            external_reference=existing.external_reference,
            customer_note=None,
            internal_note=None,
            idempotency_key=existing.idempotency_key,
        )


@pytest.mark.asyncio
async def test_payment_idempotency_is_workspace_scoped_by_actual_queries():
    workspace_a = uuid4()
    workspace_b = uuid4()
    key = "same-literal-key"
    payment_a = payment(workspace_a, 99000, key=key)
    subscription_a = subscription()
    subscription_a.workspace_id = workspace_a
    subscription_b = subscription()
    subscription_b.workspace_id = workspace_b
    db = StatefulCommercialUoW(
        payments=[payment_a],
        subscriptions=[subscription_a, subscription_b],
    )

    payment_b = await billing.create_manual_payment(
        db,
        workspace_id=workspace_b,
        method=payment_a.method,
        amount_minor=payment_a.amount_minor,
        currency=payment_a.currency,
        received_at=payment_a.received_at,
        external_reference=payment_a.external_reference,
        customer_note=payment_a.customer_note,
        internal_note=payment_a.internal_note,
        idempotency_key=key,
    )
    assert payment_b.workspace_id == workspace_b
    assert payment_b.id != payment_a.id
    assert {
        (item.workspace_id, item.idempotency_key)
        for item in db.payment_rows()
    } == {
        (workspace_a, key),
        (workspace_b, key),
    }

    replay_b = await billing.create_manual_payment(
        db,
        workspace_id=workspace_b,
        method=payment_a.method,
        amount_minor=payment_a.amount_minor,
        currency=payment_a.currency,
        received_at=payment_a.received_at,
        external_reference=payment_a.external_reference,
        customer_note=payment_a.customer_note,
        internal_note=payment_a.internal_note,
        idempotency_key=key,
    )
    assert replay_b.id == payment_b.id
    assert replay_b.workspace_id == workspace_b
    assert len(db.payment_rows()) == 2

    with pytest.raises(billing.CommercialConflict):
        await billing.create_manual_payment(
            db,
            workspace_id=workspace_b,
            method=payment_a.method,
            amount_minor=payment_a.amount_minor + 1,
            currency=payment_a.currency,
            received_at=payment_a.received_at,
            external_reference=payment_a.external_reference,
            customer_note=payment_a.customer_note,
            internal_note=payment_a.internal_note,
            idempotency_key=key,
        )
    assert db.reload_payment(payment_a.id).workspace_id == workspace_a


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("target", "selection", "amount"),
    [
        (plan("pro", 139900, 99000), "list", 139900),
        (plan("pro", 139900, 99000), "promotion", 99000),
        (plan("business", 399000), "list", 399000),
    ],
)
async def test_free_activation_behavior(
    monkeypatch, target, selection, amount
):
    sub = subscription()
    record = payment(sub.workspace_id, amount)
    now = moment(2026, 8, 25)
    db, result = await confirm(
        monkeypatch,
        sub,
        record,
        target,
        None,
        now=now,
        price_selection=selection,
    )
    assert result.subscription.plan_code == target.code
    assert result.subscription.status == "active"
    assert result.subscription.starts_at == now
    assert result.subscription.expires_at == moment(2026, 9, 25)
    assert result.subscription.renewal_price_minor == amount
    assert result.subscription.entitlement_version == 2
    assert result.payment.status == "confirmed"
    assert len(db.added) == 1
    assert db.added[0].action == "payment_confirmed"


@pytest.mark.asyncio
async def test_same_plan_early_renewal_appends_one_calendar_segment(monkeypatch):
    start = moment(2026, 8, 2)
    expiry = moment(2026, 9, 2)
    sub = subscription(
        plan_code="pro",
        starts_at=start,
        expires_at=expiry,
        renewal_price_minor=99000,
        pricing_source="catalog_promotion",
        version=2,
    )
    old_payment = uuid4()
    before = composition_for(sub, [(start, expiry, 99000, old_payment)])
    record = payment(sub.workspace_id, 99000)
    db, result = await confirm(
        monkeypatch,
        sub,
        record,
        plan("pro", 139900, 99000),
        before,
        now=moment(2026, 8, 20),
    )
    assert result.subscription.starts_at == start
    assert result.subscription.expires_at == moment(2026, 10, 2)
    assert result.subscription.renewal_price_minor == 99000
    assert result.subscription.entitlement_version == 3
    assert len(result.composition["segments"]) == 2
    assert result.composition["segments"][0]["segment_end"].startswith(
        "2026-09-02"
    )
    assert result.composition["segments"][1]["segment_start"].startswith(
        "2026-09-02"
    )
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_advance_renewal_upgrade_prices_each_segment_and_preserves_horizon(
    monkeypatch,
):
    first_start = moment(2026, 8, 2)
    boundary = moment(2026, 9, 2)
    expiry = moment(2026, 10, 2)
    effective = moment(2026, 8, 25)
    sub = subscription(
        plan_code="pro",
        starts_at=first_start,
        expires_at=expiry,
        renewal_price_minor=139900,
        pricing_source="catalog_list",
        version=4,
    )
    first_payment = uuid4()
    second_payment = uuid4()
    before = composition_for(sub, [
        (first_start, boundary, 99000, first_payment),
        (boundary, expiry, 139900, second_payment),
    ])
    raw = billing.prorated_difference_minor(
        source_price_minor=99000,
        target_price_minor=399000,
        segment_start=first_start,
        segment_end=boundary,
        effective_at=effective,
    ) + billing.prorated_difference_minor(
        source_price_minor=139900,
        target_price_minor=399000,
        segment_start=boundary,
        segment_end=expiry,
        effective_at=effective,
    )
    record = payment(sub.workspace_id, billing.round_minor_units(raw))
    db, result = await confirm(
        monkeypatch,
        sub,
        record,
        plan("business", 399000),
        before,
        now=effective,
    )
    assert result.subscription.plan_code == "business"
    assert result.subscription.expires_at == expiry
    assert result.subscription.renewal_price_minor == 399000
    assert result.subscription.entitlement_version == 5
    assert [
        item["historically_applicable_price_minor"]
        for item in result.composition["segments"]
    ] == [399000, 399000]
    assert [
        item["payment_record_id"]
        for item in result.composition["segments"]
    ] == [str(first_payment), str(second_payment)]
    assert {
        item["transition_payment_record_id"]
        for item in result.composition["segments"]
    } == {str(record.id)}
    transition = db.added[0].after_snapshot_json["transition"]
    assert [item["source_price_minor"] for item in transition[
        "segment_calculations"
    ]] == [99000, 139900]
    assert transition["expires_at_before"] == transition["expires_at_after"]


@pytest.mark.asyncio
async def test_upgrade_before_term_start_fails_closed(monkeypatch):
    start = moment(2026, 9, 2)
    expiry = moment(2026, 10, 2)
    sub = subscription(
        plan_code="pro",
        starts_at=start,
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    before = composition_for(sub, [(start, expiry, 99000, uuid4())])
    record = payment(sub.workspace_id, 310000)
    with pytest.raises(billing.CommercialValidationError):
        await confirm(
            monkeypatch,
            sub,
            record,
            plan("business", 399000),
            before,
            now=moment(2026, 8, 25),
        )
    assert record.status == "pending"
    assert sub.plan_code == "pro"
    assert sub.entitlement_version == 2


@pytest.mark.asyncio
async def test_upgrade_before_first_outstanding_segment_fails_closed(
    monkeypatch,
):
    commercial_start = moment(2026, 8, 2)
    segment_start = moment(2026, 9, 2)
    expiry = moment(2026, 10, 2)
    sub = subscription(
        plan_code="pro",
        starts_at=commercial_start,
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    before = composition_for(sub, [
        (segment_start, expiry, 99000, uuid4())
    ])
    record = payment(sub.workspace_id, 310000)
    with pytest.raises(billing.CommercialValidationError):
        await confirm(
            monkeypatch,
            sub,
            record,
            plan("business", 399000),
            before,
            now=moment(2026, 8, 25),
        )
    assert sub.plan_code == "pro"
    assert record.status == "pending"


@pytest.mark.asyncio
async def test_upgrade_exactly_at_segment_start_is_valid(monkeypatch):
    start = moment(2026, 8, 25)
    expiry = moment(2026, 9, 25)
    sub = subscription(
        plan_code="pro",
        starts_at=start,
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    before = composition_for(sub, [(start, expiry, 99000, uuid4())])
    record = payment(sub.workspace_id, 300000)
    _, result = await confirm(
        monkeypatch,
        sub,
        record,
        plan("business", 399000),
        before,
        now=start,
    )
    assert result.payment.amount_minor == 300000
    assert result.subscription.plan_code == "business"
    assert result.subscription.expires_at == expiry
    assert result.subscription.renewal_price_minor == 399000


@pytest.mark.asyncio
async def test_upgrade_just_before_expiry_uses_positive_proration(monkeypatch):
    start = moment(2026, 8, 2)
    expiry = moment(2026, 9, 2)
    effective = expiry - timedelta(minutes=1)
    sub = subscription(
        plan_code="pro",
        starts_at=start,
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    before = composition_for(sub, [(start, expiry, 99000, uuid4())])
    required = billing.round_minor_units(
        billing.prorated_difference_minor(
            source_price_minor=99000,
            target_price_minor=399000,
            segment_start=start,
            segment_end=expiry,
            effective_at=effective,
        )
    )
    assert required > 0
    record = payment(sub.workspace_id, required)
    _, result = await confirm(
        monkeypatch,
        sub,
        record,
        plan("business", 399000),
        before,
        now=effective,
    )
    assert result.subscription.plan_code == "business"
    assert result.subscription.expires_at == expiry


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [timedelta(0), timedelta(seconds=1)])
async def test_upgrade_at_or_after_expiry_uses_new_term(monkeypatch, offset):
    start = moment(2026, 8, 2)
    expiry = moment(2026, 9, 2)
    sub = subscription(
        plan_code="pro",
        starts_at=start,
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    before = composition_for(sub, [(start, expiry, 99000, uuid4())])
    effective = expiry + offset
    record = payment(sub.workspace_id, 399000)
    _, result = await confirm(
        monkeypatch,
        sub,
        record,
        plan("business", 399000),
        before,
        now=effective,
    )
    assert result.subscription.starts_at == effective
    assert result.subscription.expires_at == billing.add_one_month(effective)
    assert result.subscription.renewal_price_minor == 399000
    assert len(result.composition["segments"]) == 1


@pytest.mark.asyncio
async def test_confirmed_replay_survives_later_version_without_mutation(
    monkeypatch,
):
    original = subscription()
    record = payment(original.workspace_id, 99000)
    db, first = await confirm(
        monkeypatch,
        original,
        record,
        plan("pro", 139900, 99000),
        None,
        now=moment(2026, 8, 25),
        price_selection="promotion",
    )
    audit = db.added[0]
    assert first.subscription.entitlement_version == 2

    current = subscription(
        plan_code="business",
        starts_at=moment(2026, 8, 26),
        expires_at=moment(2026, 9, 26),
        renewal_price_minor=399000,
        pricing_source="catalog_list",
        version=5,
    )
    current.workspace_id = original.workspace_id
    current_composition = composition_for(current, [
        (current.starts_at, current.expires_at, 399000, uuid4())
    ])

    async def locked(db, workspace_id):
        return current

    async def load(db, sub):
        return current_composition

    monkeypatch.setattr(billing, "_locked_subscription", locked)
    monkeypatch.setattr(billing, "load_authoritative_composition", load)
    replay_db = QueueDB(FakeResult(values=[audit]))
    replay = await billing._confirmed_replay(
        replay_db,
        record,
        target_plan_code="pro",
        price_selection="promotion",
    )
    assert replay.idempotent_replay is True
    assert replay.subscription is current
    assert current.plan_code == "business"
    assert current.entitlement_version == 5
    assert replay_db.added == []
    with pytest.raises(billing.CommercialConflict):
        await billing._confirmed_replay(
            QueueDB(FakeResult(values=[audit])),
            record,
            target_plan_code="business",
            price_selection="list",
        )


@pytest.mark.asyncio
async def test_exact_immediate_confirmation_replay_is_side_effect_free(
    monkeypatch,
):
    sub = subscription()
    record = payment(sub.workspace_id, 139900)
    first_db, first = await confirm(
        monkeypatch,
        sub,
        record,
        plan("pro", 139900, 99000),
        None,
        now=moment(2026, 8, 25),
    )
    audit = first_db.added[0]
    version = sub.entitlement_version
    expiry = sub.expires_at
    composition = first.composition

    async def locked(db, workspace_id):
        return sub

    async def load(db, current):
        return composition

    monkeypatch.setattr(billing, "_locked_subscription", locked)
    monkeypatch.setattr(billing, "load_authoritative_composition", load)
    replay_db = QueueDB(FakeResult(record), FakeResult(values=[audit]))
    replay = await billing.confirm_manual_payment(
        replay_db,
        workspace_id=sub.workspace_id,
        payment_id=record.id,
        target_plan_code="pro",
        price_selection="list",
        actor_user_id=uuid4(),
        actor_admin_role="billing_admin",
        reason="retry",
        request_id="retry-1",
        now=moment(2026, 8, 26),
    )
    assert replay.idempotent_replay is True
    assert sub.entitlement_version == version
    assert sub.expires_at == expiry
    assert replay_db.added == []
    assert replay_db.flushes == 0


@pytest.mark.asyncio
async def test_confirmed_replay_missing_or_ambiguous_audit_fails_closed():
    record = payment(uuid4(), 99000)
    record.status = "confirmed"
    with pytest.raises(billing.CommercialCompositionError):
        await billing._confirmed_replay(
            QueueDB(FakeResult(values=[])),
            record,
            target_plan_code="pro",
            price_selection="promotion",
        )
    malformed = SimpleNamespace(
        workspace_id=record.workspace_id,
        payment_record_id=record.id,
        before_snapshot_json={},
        after_snapshot_json={},
    )
    with pytest.raises(billing.CommercialCompositionError):
        await billing._confirmed_replay(
            QueueDB(FakeResult(values=[malformed, malformed])),
            record,
            target_plan_code="pro",
            price_selection="promotion",
        )


@pytest.mark.asyncio
async def test_suspension_and_free_transitions_are_behavioral(monkeypatch):
    start = moment(2026, 8, 2)
    expiry = moment(2026, 9, 2)
    sub = subscription(
        plan_code="pro",
        starts_at=start,
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    comp = composition_for(sub, [(start, expiry, 99000, uuid4())])

    async def locked(db, workspace_id):
        return sub

    async def load(db, current):
        return comp

    monkeypatch.setattr(billing, "_locked_subscription", locked)
    monkeypatch.setattr(billing, "load_authoritative_composition", load)
    db = QueueDB()
    suspended, suspended_comp = await billing.suspend_subscription(
        db,
        workspace_id=sub.workspace_id,
        actor_user_id=uuid4(),
        actor_admin_role="subscription_admin",
        reason="risk review",
        request_id="suspend-1",
        now=moment(2026, 8, 20),
    )
    assert suspended.status == "suspended"
    assert suspended.plan_code == "pro"
    assert suspended.expires_at == expiry
    assert suspended.entitlement_version == 3
    assert suspended_comp["aggregate_version"] == 3
    assert len(db.added) == 1

    free, no_composition = await billing.transition_to_free(
        db,
        workspace_id=sub.workspace_id,
        transition="effective_cancellation",
        actor_user_id=uuid4(),
        actor_admin_role="subscription_admin",
        reason="effective cancellation",
        request_id="cancel-1",
        now=moment(2026, 8, 21),
    )
    assert free.plan_code == "free"
    assert free.status == "active"
    assert free.expires_at is None
    assert free.renewal_price_minor == 0
    assert free.entitlement_version == 4
    assert no_composition is None
    assert len(db.added) == 2


@pytest.mark.asyncio
async def test_expiry_to_free_rejects_early_and_accepts_expired(monkeypatch):
    expiry = moment(2026, 9, 2)
    sub = subscription(
        plan_code="pro",
        expires_at=expiry,
        renewal_price_minor=99000,
        version=2,
    )
    comp = composition_for(sub, [
        (sub.starts_at, expiry, 99000, uuid4())
    ])

    async def locked(db, workspace_id):
        return sub

    async def load(db, current):
        return comp

    monkeypatch.setattr(billing, "_locked_subscription", locked)
    monkeypatch.setattr(billing, "load_authoritative_composition", load)
    with pytest.raises(billing.CommercialValidationError):
        await billing.transition_to_free(
            QueueDB(),
            workspace_id=sub.workspace_id,
            transition="expiry",
            actor_user_id=uuid4(),
            actor_admin_role="subscription_admin",
            reason="expiry",
            request_id="expiry-early",
            now=expiry - timedelta(seconds=1),
        )
    db = QueueDB()
    result, _ = await billing.transition_to_free(
        db,
        workspace_id=sub.workspace_id,
        transition="expiry",
        actor_user_id=uuid4(),
        actor_admin_role="subscription_admin",
        reason="expiry",
        request_id="expiry-now",
        now=expiry,
    )
    assert result.plan_code == "free"
    assert result.expires_at is None
    assert db.added[0].action == "expiry_to_free"


def test_platform_api_routes_wire_resource_specific_dependencies():
    from app.main import app

    routes = {
        route.path: route
        for route in platform_admin_billing.router.routes
    }
    prefix = "/api/platform-admin/workspaces/{workspace_id}"
    payment_read = routes[f"{prefix}/payments/{{payment_id}}"]
    subscription_read = routes[f"{prefix}/subscription"]
    expected = {
        f"{prefix}/payments/manual": (
            platform_admin_access.require_platform_admin_payment
        ),
        f"{prefix}/payments/{{payment_id}}": (
            platform_admin_access.require_platform_admin_payment_read
        ),
        f"{prefix}/payments/{{payment_id}}/confirm": (
            platform_admin_access.require_platform_admin_payment
        ),
        f"{prefix}/subscription": (
            platform_admin_access.require_platform_admin_subscription_read
        ),
        f"{prefix}/subscription/suspend": (
            platform_admin_access.require_platform_admin_subscription
        ),
        f"{prefix}/subscription/transition-to-free": (
            platform_admin_access.require_platform_admin_subscription
        ),
    }
    openapi_paths = app.openapi()["paths"]
    expected_methods = {
        f"{prefix}/payments/manual": "post",
        f"{prefix}/payments/{{payment_id}}": "get",
        f"{prefix}/payments/{{payment_id}}/confirm": "post",
        f"{prefix}/subscription": "get",
        f"{prefix}/subscription/suspend": "post",
        f"{prefix}/subscription/transition-to-free": "post",
    }
    for path, method in expected_methods.items():
        assert method in openapi_paths[path]
    for path, gate in expected.items():
        dependencies = {
            dependency.call
            for dependency in routes[path].dependant.dependencies
        }
        assert gate in dependencies
    payment_dependencies = {
        dependency.call
        for dependency in payment_read.dependant.dependencies
    }
    subscription_dependencies = {
        dependency.call
        for dependency in subscription_read.dependant.dependencies
    }
    assert (
        platform_admin_access.require_platform_admin_payment_read
        in payment_dependencies
    )
    assert (
        platform_admin_access.require_platform_admin_subscription_read
        in subscription_dependencies
    )
    assert (
        platform_admin_access.require_platform_admin_subscription_read
        not in payment_dependencies
    )
    assert (
        platform_admin_access.require_platform_admin_payment_read
        not in subscription_dependencies
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dependency", "allowed"),
    [
        (
            platform_admin_access.require_platform_admin_payment_read,
            {"support", "billing_admin", "super_admin"},
        ),
        (
            platform_admin_access.require_platform_admin_subscription_read,
            {"support", "subscription_admin", "super_admin"},
        ),
        (
            platform_admin_access.require_platform_admin_payment,
            {"billing_admin", "super_admin"},
        ),
        (
            platform_admin_access.require_platform_admin_subscription,
            {"subscription_admin", "super_admin"},
        ),
    ],
)
async def test_platform_role_matrix_dependencies(dependency, allowed):
    user = SimpleNamespace(id=uuid4())
    for role in PlatformAdminRole:
        membership = SimpleNamespace(role=role.value)
        db = QueueDB(FakeResult(membership))
        if role.value in allowed:
            assert await dependency(user, db) is membership
        else:
            with pytest.raises(HTTPException) as exc:
                await dependency(user, db)
            assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        await dependency(user, QueueDB(FakeResult(None)))


@pytest.mark.asyncio
async def test_confirmation_route_rolls_back_persistent_uow_state(
    monkeypatch,
):
    workspace_id = uuid4()
    original_subscription = subscription()
    original_subscription.workspace_id = workspace_id
    original_payment = payment(workspace_id, 139900)
    expected_subscription = copy.deepcopy(
        vars(original_subscription)
    )
    expected_payment = copy.deepcopy(vars(original_payment))
    db = StatefulCommercialUoW(
        payments=[original_payment],
        subscriptions=[original_subscription],
        fail_on_flush=True,
    )

    async def selectable(db_arg, plan_code):
        assert db_arg is db
        assert plan_code == "pro"
        return plan("pro", 139900, 99000)

    async def no_paid_composition(db_arg, current):
        assert db_arg is db
        assert current.plan_code == "free"
        return None

    monkeypatch.setattr(billing, "_selectable_plan", selectable)
    monkeypatch.setattr(
        billing,
        "load_authoritative_composition",
        no_paid_composition,
    )

    with pytest.raises(RuntimeError, match="injected failure"):
        await platform_admin_billing.confirm_payment(
            workspace_id=workspace_id,
            payment_id=original_payment.id,
            payload=PaymentConfirmationRequest(
                target_plan_code="pro",
                reason="test rollback",
            ),
            current_user=SimpleNamespace(id=uuid4()),
            admin=SimpleNamespace(role="billing_admin"),
            db=db,
        )

    failed = db.failed_flush_state
    assert failed is not None
    assert failed["payments"][original_payment.id].status == "confirmed"
    assert failed["subscriptions"][workspace_id].plan_code == "pro"
    assert failed["subscriptions"][workspace_id].entitlement_version == 2
    assert len(failed["audits"]) == 1

    reloaded_payment = db.reload_payment(original_payment.id)
    reloaded_subscription = db.reload_subscription(workspace_id)
    assert vars(reloaded_payment) == expected_payment
    assert vars(reloaded_subscription) == expected_subscription
    assert reloaded_payment.status == PaymentStatus.pending.value
    assert reloaded_subscription.plan_code == "free"
    assert reloaded_subscription.entitlement_version == 1
    assert db.audit_rows() == []
    assert db.flushes == 1
    assert db.commits == 0
    assert db.rollbacks == 1


def test_composition_rejects_wrong_plan_and_malformed_provenance():
    sub = subscription(
        plan_code="business",
        expires_at=moment(2026, 9, 2),
        renewal_price_minor=399000,
        version=2,
    )
    wrong = billing._composition(version=2, segments=[
        billing._segment(
            start=sub.starts_at,
            end=sub.expires_at,
            plan_code="pro",
            price_minor=99000,
            currency="TWD",
            payment_record_id=uuid4(),
        )
    ])
    with pytest.raises(billing.CommercialCompositionError):
        billing._validate_composition(wrong, sub)

    valid = billing._composition(version=2, segments=[
        billing._segment(
            start=sub.starts_at,
            end=sub.expires_at,
            plan_code="business",
            price_minor=399000,
            currency="TWD",
            payment_record_id=uuid4(),
        )
    ])
    valid["segments"][0]["payment_record_id"] = "not-a-uuid"
    with pytest.raises(billing.CommercialCompositionError):
        billing._validate_composition(valid, sub)


def test_calendar_month_and_money_arithmetic():
    assert billing.add_one_month(moment(2026, 1, 31)) == moment(
        2026, 2, 28
    )
    assert billing.add_one_month(moment(2028, 1, 31)) == moment(
        2028, 2, 29
    )
    assert billing.round_minor_units(Decimal("1.5")) == 2
    assert billing.round_minor_units(Decimal("1.49")) == 1


def test_service_is_flush_only_and_uses_row_locks():
    source = inspect.getsource(billing)
    assert "db.commit" not in source
    assert "db.rollback" not in source
    assert ".with_for_update()" in inspect.getsource(
        billing.confirm_manual_payment
    )
    assert ".with_for_update()" in inspect.getsource(
        billing._locked_subscription
    )


def test_migration_is_irreversible_and_enforces_expiry_invariant():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions"
        / "e8f3a1c6d2b4_make_workspace_subscription_expiry_nullable.py"
    )
    source = path.read_text()
    normalized_source = " ".join(source.split())
    spec = importlib.util.spec_from_file_location("p2_expiry_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "e8f3a1c6d2b4"
    assert migration.down_revision == "d4c8f2a91b70"
    assert "nullable=True" in source
    assert "WHERE plan_code = 'free'" in source
    assert "ck_workspace_subscriptions_commercial_expiry" in source
    assert "plan_code <> 'free' AND expires_at IS NOT NULL" in normalized_source
    assert "raise RuntimeError" in source
