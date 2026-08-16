import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    memberships = relationship(
        "Membership",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    brands = relationship(
        "Brand",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
