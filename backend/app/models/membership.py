import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class MembershipRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    manager = "manager"
    editor = "editor"
    viewer = "viewer"


class Membership(Base):
    __tablename__ = "memberships"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "workspace_id",
            name="uq_membership_user_workspace",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[MembershipRole] = mapped_column(
        Enum(MembershipRole, name="membership_role"),
        default=MembershipRole.viewer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="memberships",
    )

    workspace = relationship(
        "Workspace",
        back_populates="memberships",
    )
