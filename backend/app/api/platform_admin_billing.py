from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.platform_admin_access import (
    require_platform_admin_payment,
    require_platform_admin_payment_read,
    require_platform_admin_subscription_read,
    require_platform_admin_subscription,
)
from app.core.database import get_db
from app.models.commercial import PlatformAdminMembership
from app.models.subscription import WorkspaceSubscription
from app.models.payment_request import PaymentRequest
from app.models.user import User
from app.schemas.commercial import (
    ManualPaymentCreateRequest,
    PaymentConfirmationRequest,
    PaymentConfirmationResponse,
    PaymentRecordListResponse,
    PaymentRecordResponse,
    PlatformSubscriptionResponse,
    SubscriptionActionRequest,
    TransitionToFreeRequest,
)
from app.services.commercial_billing import (
    CommercialCompositionError,
    CommercialConflict,
    CommercialNotFound,
    CommercialValidationError,
    confirm_manual_payment,
    create_manual_payment,
    get_payment,
    get_subscription,
    list_payments,
    suspend_subscription,
    transition_to_free,
)


router = APIRouter(
    prefix="/api/platform-admin/workspaces/{workspace_id}",
    tags=["Platform Commercial Administration"],
)


def _raise_commercial_error(exc: Exception) -> None:
    if isinstance(exc, CommercialNotFound):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (CommercialConflict, CommercialCompositionError)):
        code = status.HTTP_409_CONFLICT
    elif isinstance(exc, CommercialValidationError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        raise exc
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def _subscription_response(
    subscription: WorkspaceSubscription,
    composition: dict[str, Any] | None,
) -> PlatformSubscriptionResponse:
    return PlatformSubscriptionResponse(
        workspace_id=subscription.workspace_id,
        plan_code=subscription.plan_code,
        status=subscription.status,
        starts_at=subscription.starts_at,
        expires_at=subscription.expires_at,
        renewal_price_minor=subscription.renewal_price_minor,
        billing_currency=subscription.billing_currency,
        pricing_source=subscription.pricing_source,
        entitlement_version=subscription.entitlement_version,
        suspended_at=subscription.suspended_at,
        cancelled_at=subscription.cancelled_at,
        cancellation_effective_at=subscription.cancellation_effective_at,
        commercial_term_composition_v1=composition,
    )


@router.post(
    "/payments/manual",
    response_model=PaymentRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_manual_payment(
    workspace_id: UUID,
    payload: ManualPaymentCreateRequest,
    admin: PlatformAdminMembership = Depends(require_platform_admin_payment),
    db: AsyncSession = Depends(get_db),
):
    try:
        payment = await create_manual_payment(
            db,
            workspace_id=workspace_id,
            method=payload.method,
            amount_minor=payload.amount_minor,
            currency=payload.currency,
            received_at=payload.received_at,
            external_reference=payload.external_reference,
            customer_note=payload.customer_note,
            internal_note=payload.internal_note,
            idempotency_key=payload.idempotency_key,
        )
        await db.commit()
    except (CommercialNotFound, CommercialConflict, CommercialCompositionError, CommercialValidationError) as exc:
        await db.rollback()
        _raise_commercial_error(exc)
    except Exception:
        await db.rollback()
        raise
    return PaymentRecordResponse.model_validate(payment)


@router.get(
    "/payments",
    response_model=PaymentRecordListResponse,
)
async def read_payments(
    workspace_id: UUID,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|confirmed|rejected|refunded)$",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: PlatformAdminMembership = Depends(
        require_platform_admin_payment_read
    ),
    db: AsyncSession = Depends(get_db),
):
    payments, total = await list_payments(
        db,
        workspace_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return PaymentRecordListResponse(
        items=[
            PaymentRecordResponse.model_validate(item)
            for item in payments
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentRecordResponse,
)
async def read_payment(
    workspace_id: UUID,
    payment_id: UUID,
    admin: PlatformAdminMembership = Depends(require_platform_admin_payment_read),
    db: AsyncSession = Depends(get_db),
):
    try:
        payment = await get_payment(db, workspace_id, payment_id)
    except CommercialNotFound as exc:
        _raise_commercial_error(exc)
    return PaymentRecordResponse.model_validate(payment)


@router.post(
    "/payments/{payment_id}/confirm",
    response_model=PaymentConfirmationResponse,
)
async def confirm_payment(
    workspace_id: UUID,
    payment_id: UUID,
    payload: PaymentConfirmationRequest,
    current_user: User = Depends(get_current_user),
    admin: PlatformAdminMembership = Depends(require_platform_admin_payment),
    db: AsyncSession = Depends(get_db),
):
    try:
        target_plan_code = payload.target_plan_code.strip().lower()

        result = await confirm_manual_payment(
            db,
            workspace_id=workspace_id,
            payment_id=payment_id,
            target_plan_code=target_plan_code,
            price_selection=payload.price_selection.value,
            actor_user_id=current_user.id,
            actor_admin_role=admin.role,
            reason=payload.reason,
            request_id=payload.request_id,
        )

        request_result = await db.execute(
            select(PaymentRequest)
            .where(
                PaymentRequest.workspace_id == workspace_id,
                PaymentRequest.requested_plan_code == target_plan_code,
                PaymentRequest.status.in_(
                    ["contacted", "payment_pending"]
                ),
            )
            .order_by(PaymentRequest.created_at.desc())
            .with_for_update()
        )
        payment_request = request_result.scalars().first()

        if payment_request is not None:
            payment_request.status = "fulfilled"
            payment_request.payment_record_id = result.payment.id

        await db.commit()
    except (CommercialNotFound, CommercialConflict, CommercialCompositionError, CommercialValidationError) as exc:
        await db.rollback()
        _raise_commercial_error(exc)
    except Exception:
        await db.rollback()
        raise
    return PaymentConfirmationResponse(
        payment=PaymentRecordResponse.model_validate(result.payment),
        subscription=_subscription_response(result.subscription, result.composition),
        idempotent_replay=result.idempotent_replay,
    )


@router.get(
    "/subscription",
    response_model=PlatformSubscriptionResponse,
)
async def read_subscription(
    workspace_id: UUID,
    admin: PlatformAdminMembership = Depends(require_platform_admin_subscription_read),
    db: AsyncSession = Depends(get_db),
):
    try:
        subscription, composition = await get_subscription(db, workspace_id)
    except (CommercialNotFound, CommercialCompositionError) as exc:
        _raise_commercial_error(exc)
    return _subscription_response(subscription, composition)


@router.post(
    "/subscription/suspend",
    response_model=PlatformSubscriptionResponse,
)
async def suspend_workspace_subscription(
    workspace_id: UUID,
    payload: SubscriptionActionRequest,
    current_user: User = Depends(get_current_user),
    admin: PlatformAdminMembership = Depends(require_platform_admin_subscription),
    db: AsyncSession = Depends(get_db),
):
    try:
        subscription, composition = await suspend_subscription(
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
            actor_admin_role=admin.role,
            reason=payload.reason,
            request_id=payload.request_id,
        )
        await db.commit()
    except (CommercialNotFound, CommercialConflict, CommercialCompositionError, CommercialValidationError) as exc:
        await db.rollback()
        _raise_commercial_error(exc)
    except Exception:
        await db.rollback()
        raise
    return _subscription_response(subscription, composition)


@router.post(
    "/subscription/transition-to-free",
    response_model=PlatformSubscriptionResponse,
)
async def transition_workspace_subscription_to_free(
    workspace_id: UUID,
    payload: TransitionToFreeRequest,
    current_user: User = Depends(get_current_user),
    admin: PlatformAdminMembership = Depends(require_platform_admin_subscription),
    db: AsyncSession = Depends(get_db),
):
    try:
        subscription, composition = await transition_to_free(
            db,
            workspace_id=workspace_id,
            transition=payload.transition.value,
            actor_user_id=current_user.id,
            actor_admin_role=admin.role,
            reason=payload.reason,
            request_id=payload.request_id,
        )
        await db.commit()
    except (CommercialNotFound, CommercialConflict, CommercialCompositionError, CommercialValidationError) as exc:
        await db.rollback()
        _raise_commercial_error(exc)
    except Exception:
        await db.rollback()
        raise
    return _subscription_response(subscription, composition)
