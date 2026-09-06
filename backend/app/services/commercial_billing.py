from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_credit import WorkspaceCreditAccount
from app.models.commercial import (
    AdminSubscriptionAudit,
    PaymentRecord,
    PaymentStatus,
)
from app.models.subscription import (
    SubscriptionPlan,
    SubscriptionStatus,
    WorkspaceSubscription,
)
from app.services.subscriptions import add_one_month, get_plan


COMPOSITION_KEY = "commercial_term_composition_v1"
COMPOSITION_SCHEMA_VERSION = 1
PAID_PLAN_CODES = {"pro", "business"}


class CommercialBillingError(RuntimeError):
    pass


class CommercialNotFound(CommercialBillingError):
    pass


class CommercialConflict(CommercialBillingError):
    pass


class CommercialValidationError(CommercialBillingError):
    pass


class CommercialCompositionError(CommercialBillingError):
    pass


@dataclass(frozen=True)
class ConfirmationResult:
    payment: PaymentRecord
    subscription: WorkspaceSubscription
    composition: dict[str, Any] | None
    idempotent_replay: bool


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _canonical_datetime(
    value: datetime | None,
    *,
    field: str,
) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise CommercialValidationError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise CommercialCompositionError(f"Invalid composition {field}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommercialCompositionError(
            f"Invalid composition {field}"
        ) from exc
    if parsed.tzinfo is None:
        raise CommercialCompositionError(
            f"Composition {field} must be timezone-aware"
        )
    return parsed


def _microseconds(value: timedelta) -> int:
    return (
        (value.days * 86_400 + value.seconds) * 1_000_000
        + value.microseconds
    )


def prorated_difference_minor(
    *,
    source_price_minor: int,
    target_price_minor: int,
    segment_start: datetime,
    segment_end: datetime,
    effective_at: datetime,
) -> Decimal:
    if target_price_minor <= source_price_minor:
        raise CommercialValidationError(
            "Target price must exceed source price for an upgrade"
        )
    if not (segment_start < segment_end):
        raise CommercialCompositionError("Invalid segment boundary")
    if effective_at >= segment_end:
        return Decimal(0)

    duration = _microseconds(segment_end - segment_start)
    if effective_at <= segment_start:
        remaining = duration
    else:
        remaining = _microseconds(segment_end - effective_at)
    if duration <= 0 or remaining <= 0 or remaining > duration:
        raise CommercialCompositionError("Invalid proration duration")

    return (
        Decimal(target_price_minor - source_price_minor)
        * Decimal(remaining)
        / Decimal(duration)
    )


def round_minor_units(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _segment(
    *,
    start: datetime,
    end: datetime,
    plan_code: str,
    price_minor: int,
    currency: str,
    payment_record_id: UUID | None,
) -> dict[str, Any]:
    return {
        "segment_start": _iso(start),
        "segment_end": _iso(end),
        "effective_plan_code": plan_code,
        "historically_applicable_price_minor": price_minor,
        "currency": currency,
        "provenance_type": (
            "P2_PAYMENT"
            if payment_record_id is not None
            else "LEGACY_BOOTSTRAP"
        ),
        "payment_record_id": (
            str(payment_record_id)
            if payment_record_id is not None
            else None
        ),
        "transition_payment_record_id": (
            str(payment_record_id)
            if payment_record_id is not None
            else None
        ),
    }


def _composition(
    *,
    version: int,
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": COMPOSITION_SCHEMA_VERSION,
        "aggregate_version": version,
        "segments": deepcopy(segments),
    }


def _validate_composition(
    value: Any,
    subscription: WorkspaceSubscription,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CommercialCompositionError("Composition is not an object")
    if subscription.plan_code not in PAID_PLAN_CODES:
        raise CommercialCompositionError("Invalid paid aggregate plan")
    if value.get("schema_version") != COMPOSITION_SCHEMA_VERSION:
        raise CommercialCompositionError("Unsupported composition version")
    if value.get("aggregate_version") != subscription.entitlement_version:
        raise CommercialCompositionError("Composition version mismatch")
    segments = value.get("segments")
    if not isinstance(segments, list) or not segments:
        raise CommercialCompositionError("Paid composition has no segments")

    previous_end: datetime | None = None
    for item in segments:
        if not isinstance(item, dict):
            raise CommercialCompositionError("Malformed composition segment")
        start = _parse_datetime(item.get("segment_start"), "segment_start")
        end = _parse_datetime(item.get("segment_end"), "segment_end")
        if start >= end:
            raise CommercialCompositionError("Invalid segment boundary")
        if previous_end is not None and start != previous_end:
            raise CommercialCompositionError("Composition segments are not contiguous")
        previous_end = end
        if item.get("effective_plan_code") != subscription.plan_code:
            raise CommercialCompositionError(
                "Composition plan does not match aggregate"
            )
        price = item.get("historically_applicable_price_minor")
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0:
            raise CommercialCompositionError("Invalid segment price")
        if item.get("currency") != subscription.billing_currency:
            raise CommercialCompositionError("Composition currency mismatch")
        provenance_type = item.get("provenance_type")
        payment_record_id = item.get("payment_record_id")
        if provenance_type == "P2_PAYMENT":
            try:
                UUID(payment_record_id)
            except (TypeError, ValueError) as exc:
                raise CommercialCompositionError(
                    "Invalid P2 payment provenance"
                ) from exc
        elif provenance_type == "LEGACY_BOOTSTRAP":
            if payment_record_id is not None:
                raise CommercialCompositionError(
                    "Legacy provenance cannot invent a payment"
                )
        else:
            raise CommercialCompositionError(
                "Invalid composition provenance type"
            )
        transition_payment_id = item.get(
            "transition_payment_record_id"
        )
        if transition_payment_id is not None:
            try:
                UUID(transition_payment_id)
            except (TypeError, ValueError) as exc:
                raise CommercialCompositionError(
                    "Invalid transition payment provenance"
                ) from exc
        if (
            provenance_type == "P2_PAYMENT"
            and transition_payment_id is None
        ):
            raise CommercialCompositionError(
                "P2 segment has no transition payment provenance"
            )

    if previous_end != subscription.expires_at:
        raise CommercialCompositionError("Composition horizon mismatch")
    return deepcopy(value)


def _legacy_single_term_composition(
    subscription: WorkspaceSubscription,
) -> dict[str, Any]:
    if (
        subscription.entitlement_version != 1
        or subscription.plan_code not in PAID_PLAN_CODES
        or subscription.status not in {
            SubscriptionStatus.active.value,
            SubscriptionStatus.suspended.value,
            SubscriptionStatus.expired.value,
        }
        or subscription.expires_at is None
        or subscription.starts_at is None
        or subscription.starts_at >= subscription.expires_at
        or subscription.renewal_price_minor <= 0
        or subscription.billing_currency != "TWD"
    ):
        raise CommercialCompositionError(
            "Legacy paid subscription is not an unambiguous single term"
        )
    return _composition(
        version=subscription.entitlement_version,
        segments=[
            _segment(
                start=subscription.starts_at,
                end=subscription.expires_at,
                plan_code=subscription.plan_code,
                price_minor=subscription.renewal_price_minor,
                currency=subscription.billing_currency,
                payment_record_id=None,
            )
        ],
    )


async def load_authoritative_composition(
    db: AsyncSession,
    subscription: WorkspaceSubscription,
) -> dict[str, Any] | None:
    if subscription.plan_code == "free":
        if subscription.expires_at is not None:
            raise CommercialCompositionError(
                "Free subscription has a commercial expiry"
            )
        return None
    if subscription.expires_at is None:
        raise CommercialCompositionError(
            "Paid subscription has no commercial expiry"
        )

    result = await db.execute(
        select(AdminSubscriptionAudit).where(
            AdminSubscriptionAudit.workspace_id
            == subscription.workspace_id
        )
    )
    candidates: list[dict[str, Any]] = []
    any_native = False
    for audit in result.scalars().all():
        snapshot = audit.after_snapshot_json
        if not isinstance(snapshot, dict):
            continue
        candidate = snapshot.get(COMPOSITION_KEY)
        if candidate is None:
            continue
        any_native = True
        if (
            isinstance(candidate, dict)
            and candidate.get("aggregate_version")
            == subscription.entitlement_version
        ):
            candidates.append(candidate)

    if len(candidates) == 1:
        return _validate_composition(candidates[0], subscription)
    if len(candidates) > 1:
        raise CommercialCompositionError(
            "Duplicate composition for aggregate version"
        )
    if any_native or subscription.entitlement_version != 1:
        raise CommercialCompositionError(
            "Current aggregate composition is missing"
        )
    return _legacy_single_term_composition(subscription)


def _subscription_state(
    subscription: WorkspaceSubscription,
    composition: dict[str, Any] | None,
    *,
    transition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "workspace_id": str(subscription.workspace_id),
        "plan_code": subscription.plan_code,
        "status": subscription.status,
        "starts_at": _iso(subscription.starts_at),
        "expires_at": _iso(subscription.expires_at),
        "renewal_price_minor": subscription.renewal_price_minor,
        "billing_currency": subscription.billing_currency,
        "pricing_source": subscription.pricing_source,
        "entitlement_version": subscription.entitlement_version,
        COMPOSITION_KEY: deepcopy(composition),
    }
    if transition is not None:
        value["transition"] = deepcopy(transition)
    return value


async def _locked_subscription(
    db: AsyncSession,
    workspace_id: UUID,
) -> WorkspaceSubscription:
    result = await db.execute(
        select(WorkspaceSubscription)
        .where(WorkspaceSubscription.workspace_id == workspace_id)
        .with_for_update()
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise CommercialNotFound("Workspace subscription not found")
    return subscription


async def _selectable_plan(
    db: AsyncSession,
    plan_code: str,
) -> SubscriptionPlan:
    plan = await get_plan(db, plan_code)
    if plan is None or not plan.is_active or not plan.is_public:
        raise CommercialValidationError("Target plan is not selectable")
    if plan.code not in PAID_PLAN_CODES or plan.currency != "TWD":
        raise CommercialValidationError("Target paid plan is unsupported")
    return plan


def _catalog_price(plan: SubscriptionPlan, selection: str) -> tuple[int, str]:
    if selection == "promotion":
        if plan.code != "pro" or plan.promotional_price_minor is None:
            raise CommercialValidationError("Promotion is not available")
        return plan.promotional_price_minor, "catalog_promotion"
    if selection != "list":
        raise CommercialValidationError("Invalid price selection")
    return plan.list_price_minor, "catalog_list"


def _payment_material(payment: PaymentRecord) -> tuple[Any, ...]:
    return (
        payment.method,
        payment.amount_minor,
        payment.currency,
        payment.received_at,
        payment.external_reference,
        payment.customer_note,
        payment.internal_note,
    )


async def create_manual_payment(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    method: str,
    amount_minor: int,
    currency: str,
    received_at: datetime | None,
    external_reference: str | None,
    customer_note: str | None,
    internal_note: str | None,
    idempotency_key: str,
    now: datetime | None = None,
) -> PaymentRecord:
    if amount_minor <= 0 or currency != "TWD":
        raise CommercialValidationError("Invalid payment amount or currency")
    await _locked_subscription(db, workspace_id)
    timestamp = _canonical_datetime(
        now or utcnow(),
        field="payment timestamp",
    )
    received_at = _canonical_datetime(
        received_at,
        field="received_at",
    )
    payment_id = uuid4()
    stmt = (
        insert(PaymentRecord)
        .values(
            id=payment_id,
            workspace_id=workspace_id,
            source="manual",
            method=method,
            amount_minor=amount_minor,
            currency=currency,
            status=PaymentStatus.pending.value,
            received_at=received_at,
            confirmed_at=None,
            confirmed_by_admin_user_id=None,
            external_reference=external_reference,
            customer_note=customer_note,
            internal_note=internal_note,
            idempotency_key=idempotency_key,
            created_at=timestamp,
            updated_at=timestamp,
        )
        .on_conflict_do_nothing(
            index_elements=["workspace_id", "idempotency_key"]
        )
    )
    await db.execute(stmt)
    result = await db.execute(
        select(PaymentRecord).where(
            PaymentRecord.workspace_id == workspace_id,
            PaymentRecord.idempotency_key == idempotency_key,
        )
    )
    payment = result.scalar_one()
    requested = (
        method,
        amount_minor,
        currency,
        received_at,
        external_reference,
        customer_note,
        internal_note,
    )
    if payment.source != "manual" or _payment_material(payment) != requested:
        raise CommercialConflict("Payment idempotency conflict")
    await db.flush()
    return payment


async def get_payment(
    db: AsyncSession,
    workspace_id: UUID,
    payment_id: UUID,
) -> PaymentRecord:
    result = await db.execute(
        select(PaymentRecord).where(
            PaymentRecord.id == payment_id,
            PaymentRecord.workspace_id == workspace_id,
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise CommercialNotFound("Payment not found")
    return payment


async def list_payments(
    db: AsyncSession,
    workspace_id: UUID,
    *,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[PaymentRecord], int]:
    filters = [
        PaymentRecord.workspace_id == workspace_id,
    ]
    if status is not None:
        filters.append(PaymentRecord.status == status)

    total_result = await db.execute(
        select(func.count(PaymentRecord.id)).where(*filters)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(PaymentRecord)
        .where(*filters)
        .order_by(
            PaymentRecord.created_at.desc(),
            PaymentRecord.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total


async def get_subscription(
    db: AsyncSession,
    workspace_id: UUID,
) -> tuple[WorkspaceSubscription, dict[str, Any] | None]:
    result = await db.execute(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id
        )
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        raise CommercialNotFound("Workspace subscription not found")
    return subscription, await load_authoritative_composition(db, subscription)


async def _confirmed_replay(
    db: AsyncSession,
    payment: PaymentRecord,
    *,
    target_plan_code: str,
    price_selection: str,
) -> ConfirmationResult:
    result = await db.execute(
        select(AdminSubscriptionAudit).where(
            AdminSubscriptionAudit.payment_record_id == payment.id,
            AdminSubscriptionAudit.action == "payment_confirmed",
        )
    )
    audits = list(result.scalars().all())
    if len(audits) != 1:
        raise CommercialCompositionError(
            "Confirmed payment audit evidence is inconsistent"
        )
    audit = audits[0]
    before = audit.before_snapshot_json
    after = audit.after_snapshot_json
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise CommercialCompositionError(
            "Confirmed payment audit snapshots are malformed"
        )
    transition = after.get("transition")
    if not isinstance(transition, dict):
        raise CommercialCompositionError(
            "Confirmed payment transition evidence is malformed"
        )
    expected_payment_id = str(payment.id)
    if (
        audit.workspace_id != payment.workspace_id
        or audit.payment_record_id != payment.id
        or before.get("workspace_id") != str(payment.workspace_id)
        or after.get("workspace_id") != str(payment.workspace_id)
        or transition.get("payment_record_id") != expected_payment_id
        or transition.get("source_plan_code") != before.get("plan_code")
    ):
        raise CommercialCompositionError(
            "Confirmed payment audit linkage is inconsistent"
        )
    if (
        transition.get("target_plan_code") != target_plan_code
        or transition.get("price_selection") != price_selection
    ):
        raise CommercialConflict("Confirmed payment replay conflict")
    behavior = transition.get("behavior")
    if behavior not in {
        "FULL_TERM_ACTIVATION",
        "SAME_PLAN_RENEWAL",
        "EXPIRED_OR_LAPSED_REACTIVATION",
        "MID_CYCLE_PAID_UPGRADE",
    }:
        raise CommercialCompositionError(
            "Confirmed payment operation is invalid"
        )
    target_full_price = transition.get(
        "target_full_monthly_price_minor"
    )
    actual_amount = transition.get("actual_payment_amount_minor")
    if (
        payment.source != "manual"
        or payment.status != PaymentStatus.confirmed.value
        or isinstance(target_full_price, bool)
        or not isinstance(target_full_price, int)
        or target_full_price <= 0
        or actual_amount != payment.amount_minor
        or after.get("renewal_price_minor") != target_full_price
        or after.get("billing_currency") != payment.currency
        or after.get("plan_code") != target_plan_code
    ):
        raise CommercialConflict(
            "Confirmed payment financial evidence conflicts"
        )
    if behavior == "MID_CYCLE_PAID_UPGRADE":
        if transition.get("total_top_up_minor") != payment.amount_minor:
            raise CommercialConflict(
                "Confirmed upgrade top-up evidence conflicts"
            )
    elif target_full_price != payment.amount_minor:
        raise CommercialConflict(
            "Confirmed full-term payment evidence conflicts"
        )
    effective_at = _parse_datetime(
        transition.get("effective_at"),
        "effective_at",
    )
    confirmed_at = _canonical_datetime(
        payment.confirmed_at,
        field="confirmed_at",
    )
    if confirmed_at is None or effective_at.astimezone(timezone.utc) != confirmed_at:
        raise CommercialCompositionError(
            "Confirmed payment timestamp evidence is inconsistent"
        )
    resulting_version = after.get("entitlement_version")
    if isinstance(resulting_version, bool) or not isinstance(resulting_version, int):
        raise CommercialCompositionError(
            "Confirmed payment aggregate version is invalid"
        )
    historical_expiry = _parse_datetime(after.get("expires_at"), "expires_at")
    historical_subscription = type(
        "HistoricalSubscriptionEvidence",
        (),
        {
            "entitlement_version": resulting_version,
            "plan_code": after.get("plan_code"),
            "billing_currency": after.get("billing_currency"),
            "expires_at": historical_expiry,
        },
    )()
    historical_composition = after.get(COMPOSITION_KEY)
    _validate_composition(
        historical_composition,
        historical_subscription,
    )

    # Lock and return the present aggregate without replaying historical state.
    subscription = await _locked_subscription(db, payment.workspace_id)
    composition = await load_authoritative_composition(db, subscription)
    return ConfirmationResult(payment, subscription, composition, True)


async def confirm_manual_payment(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    payment_id: UUID,
    target_plan_code: str,
    price_selection: str,
    actor_user_id: UUID,
    actor_admin_role: str,
    reason: str,
    request_id: str | None,
    now: datetime | None = None,
) -> ConfirmationResult:
    effective_at = _canonical_datetime(
        now or utcnow(),
        field="confirmation timestamp",
    )
    payment_result = await db.execute(
        select(PaymentRecord)
        .where(
            PaymentRecord.id == payment_id,
            PaymentRecord.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    payment = payment_result.scalar_one_or_none()
    if payment is None:
        raise CommercialNotFound("Payment not found")
    if payment.status == PaymentStatus.confirmed.value:
        return await _confirmed_replay(
            db,
            payment,
            target_plan_code=target_plan_code,
            price_selection=price_selection,
        )
    if payment.status != PaymentStatus.pending.value:
        raise CommercialConflict("Payment cannot be confirmed")

    account_result = await db.execute(
        select(WorkspaceCreditAccount)
        .where(
            WorkspaceCreditAccount.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    credit_account = account_result.scalar_one_or_none()
    if credit_account is None:
        raise CommercialCompositionError("Credit account is missing")

    subscription = await _locked_subscription(db, workspace_id)
    plan = await _selectable_plan(db, target_plan_code)
    before_composition = await load_authoritative_composition(db, subscription)
    before_state = _subscription_state(subscription, before_composition)
    old_expiry = subscription.expires_at
    old_plan = subscription.plan_code
    transition: dict[str, Any] = {
        "target_plan_code": plan.code,
        "price_selection": price_selection,
        "effective_at": _iso(effective_at),
        "payment_record_id": str(payment.id),
    }

    if old_plan == "free":
        target_price, pricing_source = _catalog_price(plan, price_selection)
        if payment.amount_minor != target_price:
            raise CommercialValidationError("Payment amount does not match activation price")
        behavior = "FULL_TERM_ACTIVATION"
        term_end = add_one_month(effective_at)
        new_segments = [_segment(
            start=effective_at,
            end=term_end,
            plan_code=plan.code,
            price_minor=target_price,
            currency="TWD",
            payment_record_id=payment.id,
        )]
        subscription.starts_at = effective_at
        subscription.expires_at = term_end
    elif old_plan == plan.code:
        if old_plan not in PAID_PLAN_CODES or subscription.expires_at is None:
            raise CommercialCompositionError("Paid renewal state is invalid")
        if subscription.expires_at > effective_at and subscription.status == SubscriptionStatus.active.value:
            behavior = "SAME_PLAN_RENEWAL"
            target_price = subscription.renewal_price_minor
            pricing_source = subscription.pricing_source or "locked_renewal"
            if payment.amount_minor != target_price:
                raise CommercialValidationError("Payment amount does not match locked renewal price")
            if before_composition is None:
                raise CommercialCompositionError("Renewal composition is missing")
            new_segments = [
                deepcopy(item)
                for item in before_composition["segments"]
                if _parse_datetime(item["segment_end"], "segment_end")
                > effective_at
            ]
            if not new_segments:
                raise CommercialCompositionError(
                    "Renewal composition has no outstanding segment"
                )
            segment_start = subscription.expires_at
            segment_end = add_one_month(segment_start)
            new_segments.append(_segment(
                start=segment_start,
                end=segment_end,
                plan_code=plan.code,
                price_minor=target_price,
                currency=subscription.billing_currency,
                payment_record_id=payment.id,
            ))
            subscription.expires_at = segment_end
        else:
            behavior = "EXPIRED_OR_LAPSED_REACTIVATION"
            target_price, pricing_source = _catalog_price(plan, price_selection)
            if payment.amount_minor != target_price:
                raise CommercialValidationError("Payment amount does not match reactivation price")
            term_end = add_one_month(effective_at)
            new_segments = [_segment(
                start=effective_at,
                end=term_end,
                plan_code=plan.code,
                price_minor=target_price,
                currency="TWD",
                payment_record_id=payment.id,
            )]
            subscription.starts_at = effective_at
            subscription.expires_at = term_end
    elif old_plan == "pro" and plan.code == "business":
        if (
            subscription.status == SubscriptionStatus.active.value
            and subscription.expires_at is not None
            and subscription.expires_at > effective_at
        ):
            behavior = "MID_CYCLE_PAID_UPGRADE"
            target_price, pricing_source = _catalog_price(plan, price_selection)
            if before_composition is None:
                raise CommercialCompositionError("Upgrade composition is missing")
            outstanding = [
                item
                for item in before_composition["segments"]
                if _parse_datetime(item["segment_end"], "segment_end")
                > effective_at
            ]
            if not outstanding:
                raise CommercialCompositionError(
                    "Upgrade composition has no outstanding segment"
                )
            first_start = _parse_datetime(
                outstanding[0]["segment_start"],
                "segment_start",
            )
            if (
                subscription.starts_at is None
                or effective_at < subscription.starts_at
                or effective_at < first_start
                or not any(
                    _parse_datetime(item["segment_start"], "segment_start")
                    <= effective_at
                    < _parse_datetime(item["segment_end"], "segment_end")
                    for item in outstanding
                )
            ):
                raise CommercialValidationError(
                    "Upgrade effective time is outside the active commercial term"
                )
            total = Decimal(0)
            calculations: list[dict[str, Any]] = []
            new_segments = []
            for item in before_composition["segments"]:
                start = _parse_datetime(item["segment_start"], "segment_start")
                end = _parse_datetime(item["segment_end"], "segment_end")
                if end <= effective_at:
                    continue
                source_price = item["historically_applicable_price_minor"]
                raw = prorated_difference_minor(
                    source_price_minor=source_price,
                    target_price_minor=target_price,
                    segment_start=start,
                    segment_end=end,
                    effective_at=effective_at,
                )
                total += raw
                calculations.append({
                    "segment_start": _iso(start),
                    "segment_end": _iso(end),
                    "source_plan_code": item["effective_plan_code"],
                    "source_price_minor": source_price,
                    "source_provenance_type": item["provenance_type"],
                    "source_payment_record_id": item["payment_record_id"],
                    "target_price_minor": target_price,
                    "transition_payment_record_id": str(payment.id),
                    "unrounded_top_up_minor": format(raw, "f"),
                })
                upgraded = deepcopy(item)
                upgraded["effective_plan_code"] = plan.code
                upgraded[
                    "historically_applicable_price_minor"
                ] = target_price
                upgraded[
                    "transition_payment_record_id"
                ] = str(payment.id)
                new_segments.append(upgraded)
            required = round_minor_units(total)
            if required <= 0 or payment.amount_minor != required:
                raise CommercialValidationError("Payment amount does not match upgrade top-up")
            transition["segment_calculations"] = calculations
            transition["total_top_up_minor"] = required
            transition["expires_at_before"] = _iso(old_expiry)
            transition["expires_at_after"] = _iso(old_expiry)
            # A true upgrade preserves the already-paid horizon.
            subscription.expires_at = old_expiry
        else:
            behavior = "EXPIRED_OR_LAPSED_REACTIVATION"
            target_price, pricing_source = _catalog_price(plan, price_selection)
            if payment.amount_minor != target_price:
                raise CommercialValidationError("Payment amount does not match reactivation price")
            term_end = add_one_month(effective_at)
            new_segments = [_segment(
                start=effective_at,
                end=term_end,
                plan_code=plan.code,
                price_minor=target_price,
                currency="TWD",
                payment_record_id=payment.id,
            )]
            subscription.starts_at = effective_at
            subscription.expires_at = term_end
    else:
        raise CommercialValidationError("Commercial plan transition is unsupported")

    if subscription.expires_at is None:
        raise CommercialCompositionError("Paid transition produced no expiry")
    subscription.plan_code = plan.code
    subscription.status = SubscriptionStatus.active.value
    subscription.activated_at = effective_at
    subscription.activated_by_user_id = actor_user_id
    subscription.suspended_at = None
    subscription.cancelled_at = None
    subscription.cancellation_effective_at = None
    subscription.renewal_price_minor = target_price
    subscription.billing_currency = "TWD"
    subscription.pricing_source = pricing_source
    subscription.entitlement_version += 1

    subscription.credits_granted = plan.monthly_credits
    if behavior in {
        "FULL_TERM_ACTIVATION",
        "EXPIRED_OR_LAPSED_REACTIVATION",
    }:
        subscription.credits_used = 0
        subscription.cycle_start = effective_at
        subscription.cycle_end = subscription.expires_at

    credit_account.balance = max(
        subscription.credits_granted - subscription.credits_used,
        0,
    )
    credit_account.updated_at = effective_at
    subscription.updated_at = effective_at

    new_composition = _composition(
        version=subscription.entitlement_version,
        segments=new_segments,
    )
    transition.update({
        "behavior": behavior,
        "source_plan_code": old_plan,
        "target_full_monthly_price_minor": target_price,
        "actual_payment_amount_minor": payment.amount_minor,
        "expires_at_before": transition.get("expires_at_before", _iso(old_expiry)),
        "expires_at_after": transition.get("expires_at_after", _iso(subscription.expires_at)),
    })
    payment.status = PaymentStatus.confirmed.value
    payment.confirmed_at = effective_at
    payment.confirmed_by_admin_user_id = actor_user_id
    payment.updated_at = effective_at

    after_state = _subscription_state(
        subscription,
        new_composition,
        transition=transition,
    )
    db.add(AdminSubscriptionAudit(
        workspace_id=workspace_id,
        payment_record_id=payment.id,
        actor_user_id=actor_user_id,
        actor_admin_role=actor_admin_role,
        action="payment_confirmed",
        reason=reason,
        support_note=None,
        before_snapshot_json=before_state,
        after_snapshot_json=after_state,
        request_id=request_id,
        created_at=effective_at,
    ))
    await db.flush()
    return ConfirmationResult(payment, subscription, new_composition, False)


async def suspend_subscription(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    actor_user_id: UUID,
    actor_admin_role: str,
    reason: str,
    request_id: str | None,
    now: datetime | None = None,
) -> tuple[WorkspaceSubscription, dict[str, Any] | None]:
    effective_at = now or utcnow()
    subscription = await _locked_subscription(db, workspace_id)
    composition = await load_authoritative_composition(db, subscription)
    if subscription.status == SubscriptionStatus.suspended.value:
        return subscription, composition
    before = _subscription_state(subscription, composition)
    subscription.status = SubscriptionStatus.suspended.value
    subscription.suspended_at = effective_at
    subscription.entitlement_version += 1
    subscription.updated_at = effective_at
    if composition is not None:
        composition["aggregate_version"] = subscription.entitlement_version
    after = _subscription_state(subscription, composition)
    db.add(AdminSubscriptionAudit(
        workspace_id=workspace_id,
        payment_record_id=None,
        actor_user_id=actor_user_id,
        actor_admin_role=actor_admin_role,
        action="subscription_suspended",
        reason=reason,
        support_note=None,
        before_snapshot_json=before,
        after_snapshot_json=after,
        request_id=request_id,
        created_at=effective_at,
    ))
    await db.flush()
    return subscription, composition


async def transition_to_free(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    transition: str,
    actor_user_id: UUID,
    actor_admin_role: str,
    reason: str,
    request_id: str | None,
    now: datetime | None = None,
) -> tuple[WorkspaceSubscription, None]:
    effective_at = now or utcnow()
    subscription = await _locked_subscription(db, workspace_id)
    if subscription.plan_code == "free":
        if subscription.status != SubscriptionStatus.active.value or subscription.expires_at is not None:
            raise CommercialCompositionError("Free aggregate is malformed")
        return subscription, None
    composition = await load_authoritative_composition(db, subscription)
    if transition == "expiry":
        if subscription.expires_at is None or subscription.expires_at > effective_at:
            raise CommercialValidationError("Paid entitlement has not expired")
        action = "expiry_to_free"
    elif transition == "effective_cancellation":
        action = "effective_cancellation_to_free"
    else:
        raise CommercialValidationError("Invalid Free transition")
    before = _subscription_state(subscription, composition)
    subscription.plan_code = "free"
    subscription.status = SubscriptionStatus.active.value
    subscription.starts_at = effective_at
    subscription.expires_at = None
    subscription.activated_at = effective_at
    subscription.activated_by_user_id = actor_user_id
    subscription.suspended_at = None
    subscription.cancelled_at = effective_at if transition == "effective_cancellation" else None
    subscription.cancellation_effective_at = effective_at if transition == "effective_cancellation" else None
    subscription.renewal_price_minor = 0
    subscription.billing_currency = "TWD"
    subscription.pricing_source = "free"
    subscription.entitlement_version += 1
    subscription.updated_at = effective_at
    after = _subscription_state(subscription, None, transition={
        "behavior": transition.upper(),
        "effective_at": _iso(effective_at),
        "source_composition": composition,
    })
    db.add(AdminSubscriptionAudit(
        workspace_id=workspace_id,
        payment_record_id=None,
        actor_user_id=actor_user_id,
        actor_admin_role=actor_admin_role,
        action=action,
        reason=reason,
        support_note=None,
        before_snapshot_json=before,
        after_snapshot_json=after,
        request_id=request_id,
        created_at=effective_at,
    ))
    await db.flush()
    return subscription, None
