from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.platform_admin_access import require_platform_admin_read
from app.api.workspace_access import require_workspace_membership
from app.core.database import get_db
from app.models.commercial import PlatformAdminMembership
from app.models.membership import Membership, MembershipRole
from app.models.payment_request import PaymentRequest
from app.models.support import (
    SupportConversation,
    SupportConversationKind,
    SupportConversationStatus,
    SupportMessage,
    utcnow,
)
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.support import (
    AdminSupportConversationResponse,
    SupportConversationCreate,
    SupportConversationResponse,
    SupportMessageCreate,
    SupportMessageResponse,
)


router = APIRouter(tags=["Support"])


def _clean_text(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} cannot be blank",
        )
    return cleaned


async def _customer_conversation(
    db: AsyncSession,
    current_user: User,
    workspace_id: UUID,
    conversation_id: UUID,
) -> SupportConversation:
    await require_workspace_membership(db, current_user, workspace_id)

    result = await db.execute(
        select(SupportConversation).where(
            SupportConversation.id == conversation_id,
            SupportConversation.workspace_id == workspace_id,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support conversation not found",
        )

    return conversation


async def _admin_conversation(
    db: AsyncSession,
    conversation_id: UUID,
    *,
    lock: bool = False,
) -> SupportConversation:
    statement = select(SupportConversation).where(
        SupportConversation.id == conversation_id,
    )

    if lock:
        statement = statement.with_for_update()

    result = await db.execute(statement)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support conversation not found",
        )

    return conversation


def _admin_conversation_response(
    conversation: SupportConversation,
    workspace: Workspace,
    owner: User,
) -> AdminSupportConversationResponse:
    payload = SupportConversationResponse.model_validate(
        conversation
    ).model_dump()

    return AdminSupportConversationResponse(
        **payload,
        workspace_name=workspace.name,
        owner_email=owner.email,
        owner_full_name=owner.full_name,
    )


@router.post(
    "/api/workspaces/{workspace_id}/support/conversations",
    response_model=SupportConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_conversation(
    workspace_id: UUID,
    payload: SupportConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)

    message_body = _clean_text(payload.message, "message")
    category = _clean_text(payload.category, "category")
    subject = (
        payload.subject.strip()
        if payload.subject and payload.subject.strip()
        else None
    )

    payment_request = None
    kind = SupportConversationKind.general.value

    if payload.payment_request_id is not None:
        payment_result = await db.execute(
            select(PaymentRequest)
            .where(
                PaymentRequest.id == payload.payment_request_id,
                PaymentRequest.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        payment_request = payment_result.scalar_one_or_none()

        if payment_request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment request not found",
            )

        existing_result = await db.execute(
            select(SupportConversation).where(
                SupportConversation.payment_request_id
                == payload.payment_request_id,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A support conversation already exists for this payment request",
            )

        kind = SupportConversationKind.payment_request.value

        if subject is None:
            subject = f"Payment plan: {payment_request.requested_plan_code}"

    now = utcnow()
    conversation = SupportConversation(
        workspace_id=workspace_id,
        payment_request_id=payload.payment_request_id,
        kind=kind,
        category=category,
        subject=subject,
        status=SupportConversationStatus.open.value,
        channel="web",
        created_by_user_id=current_user.id,
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    await db.flush()

    db.add(
        SupportMessage(
            conversation_id=conversation.id,
            sender_user_id=current_user.id,
            sender_role="customer",
            body=message_body,
            created_at=now,
        )
    )

    await db.commit()
    await db.refresh(conversation)

    return SupportConversationResponse.model_validate(conversation)


@router.get(
    "/api/workspaces/{workspace_id}/support/conversations",
    response_model=list[SupportConversationResponse],
)
async def list_customer_conversations(
    workspace_id: UUID,
    payment_request_id: UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_workspace_membership(db, current_user, workspace_id)

    statement = select(SupportConversation).where(
        SupportConversation.workspace_id == workspace_id,
    )

    if payment_request_id is not None:
        statement = statement.where(
            SupportConversation.payment_request_id
            == payment_request_id,
        )

    result = await db.execute(
        statement.order_by(SupportConversation.updated_at.desc())
    )

    return [
        SupportConversationResponse.model_validate(item)
        for item in result.scalars().all()
    ]


@router.get(
    "/api/workspaces/{workspace_id}/support/conversations/{conversation_id}/messages",
    response_model=list[SupportMessageResponse],
)
async def list_customer_messages(
    workspace_id: UUID,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _customer_conversation(
        db,
        current_user,
        workspace_id,
        conversation_id,
    )

    result = await db.execute(
        select(SupportMessage)
        .where(
            SupportMessage.conversation_id == conversation.id,
        )
        .order_by(SupportMessage.created_at.asc())
    )

    return [
        SupportMessageResponse.model_validate(item)
        for item in result.scalars().all()
    ]


@router.post(
    "/api/workspaces/{workspace_id}/support/conversations/{conversation_id}/messages",
    response_model=SupportMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer_message(
    workspace_id: UUID,
    conversation_id: UUID,
    payload: SupportMessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _customer_conversation(
        db,
        current_user,
        workspace_id,
        conversation_id,
    )

    if conversation.status == SupportConversationStatus.closed.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Support conversation is closed",
        )

    now = utcnow()
    message = SupportMessage(
        conversation_id=conversation.id,
        sender_user_id=current_user.id,
        sender_role="customer",
        body=_clean_text(payload.body, "body"),
        created_at=now,
    )
    db.add(message)

    conversation.last_message_at = now
    conversation.updated_at = now

    await db.commit()
    await db.refresh(message)

    return SupportMessageResponse.model_validate(message)


@router.get(
    "/api/platform-admin/support/conversations",
    response_model=list[AdminSupportConversationResponse],
)
async def list_admin_conversations(
    status_filter: str | None = Query(default=None, alias="status"),
    workspace_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    _admin_membership: PlatformAdminMembership = Depends(
        require_platform_admin_read
    ),
    db: AsyncSession = Depends(get_db),
):
    statement = (
        select(SupportConversation, Workspace, User)
        .join(
            Workspace,
            Workspace.id == SupportConversation.workspace_id,
        )
        .join(
            Membership,
            Membership.workspace_id == Workspace.id,
        )
        .join(
            User,
            User.id == Membership.user_id,
        )
        .where(Membership.role == MembershipRole.owner)
    )

    if status_filter is not None:
        statement = statement.where(
            SupportConversation.status == status_filter,
        )

    if workspace_id is not None:
        statement = statement.where(
            SupportConversation.workspace_id == workspace_id,
        )

    result = await db.execute(
        statement
        .order_by(SupportConversation.updated_at.desc())
        .limit(limit)
    )

    return [
        _admin_conversation_response(conversation, workspace, owner)
        for conversation, workspace, owner in result.all()
    ]


@router.get(
    "/api/platform-admin/support/conversations/{conversation_id}/messages",
    response_model=list[SupportMessageResponse],
)
async def list_admin_messages(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    _admin_membership: PlatformAdminMembership = Depends(
        require_platform_admin_read
    ),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _admin_conversation(db, conversation_id)

    result = await db.execute(
        select(SupportMessage)
        .where(
            SupportMessage.conversation_id == conversation.id,
        )
        .order_by(SupportMessage.created_at.asc())
    )

    return [
        SupportMessageResponse.model_validate(item)
        for item in result.scalars().all()
    ]


@router.post(
    "/api/platform-admin/support/conversations/{conversation_id}/messages",
    response_model=SupportMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_message(
    conversation_id: UUID,
    payload: SupportMessageCreate,
    current_user: User = Depends(get_current_user),
    _admin_membership: PlatformAdminMembership = Depends(
        require_platform_admin_read
    ),
    db: AsyncSession = Depends(get_db),
):
    conversation = await _admin_conversation(
        db,
        conversation_id,
        lock=True,
    )

    now = utcnow()

    if conversation.payment_request_id is not None:
        payment_result = await db.execute(
            select(PaymentRequest)
            .where(
                PaymentRequest.id == conversation.payment_request_id,
                PaymentRequest.workspace_id == conversation.workspace_id,
            )
            .with_for_update()
        )
        payment_request = payment_result.scalar_one_or_none()

        if payment_request is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Linked payment request is unavailable",
            )

        if payment_request.status == "requested":
            payment_request.status = "contacted"
            payment_request.updated_at = now

    conversation.status = SupportConversationStatus.open.value
    conversation.last_message_at = now
    conversation.updated_at = now

    message = SupportMessage(
        conversation_id=conversation.id,
        sender_user_id=current_user.id,
        sender_role="admin",
        body=_clean_text(payload.body, "body"),
        created_at=now,
    )
    db.add(message)

    await db.commit()
    await db.refresh(message)

    return SupportMessageResponse.model_validate(message)
