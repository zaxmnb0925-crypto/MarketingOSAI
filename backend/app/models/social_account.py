import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.core.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SocialPlatform(
    str,
    enum.Enum,
):
    instagram = "instagram"
    facebook = "facebook"
    threads = "threads"
    linkedin = "linkedin"
    x = "x"


class SocialAccountStatus(
    str,
    enum.Enum,
):
    pending = "pending"
    connected = "connected"
    expired = "expired"
    revoked = "revoked"
    error = "error"


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "platform",
            "platform_account_id",
            name=(
                "uq_social_accounts_"
                "workspace_platform_account"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    brand_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "brands.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    platform: Mapped[
        SocialPlatform
    ] = mapped_column(
        Enum(
            SocialPlatform,
            name="social_platform",
        ),
        nullable=False,
    )

    status: Mapped[
        SocialAccountStatus
    ] = mapped_column(
        Enum(
            SocialAccountStatus,
            name="social_account_status",
        ),
        nullable=False,
        default=(
            SocialAccountStatus.pending
        ),
    )

    platform_account_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    account_name: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    username: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    profile_url: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    scopes: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    access_token_ciphertext: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    refresh_token_ciphertext: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    token_expires_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_synced_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_error: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


# IMPORTANT:
# OAuth access_token / refresh_token
# intentionally do NOT exist in v0.11B.
#
# Token encryption and encrypted secret
# storage will be implemented separately
# in v0.11C.
