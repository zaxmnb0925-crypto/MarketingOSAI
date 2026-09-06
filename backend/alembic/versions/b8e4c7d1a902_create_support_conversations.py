from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8e4c7d1a902"
down_revision: Union[str, None] = "3f7a1c9e2b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_conversations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "payment_request_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "kind",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'general'"),
        ),
        sa.Column(
            "category",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "channel",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'web'"),
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('general', 'payment_request')",
            name="ck_support_conversations_kind",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'closed')",
            name="ck_support_conversations_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payment_request_id"],
            ["payment_requests.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "payment_request_id",
            name="uq_support_conversations_payment_request",
        ),
    )

    op.create_index(
        "ix_support_conversations_workspace_id",
        "support_conversations",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_support_conversations_payment_request_id",
        "support_conversations",
        ["payment_request_id"],
        unique=False,
    )
    op.create_index(
        "ix_support_conversations_workspace_updated",
        "support_conversations",
        ["workspace_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "support_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sender_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "sender_role",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "body",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sender_role IN ('customer', 'admin')",
            name="ck_support_messages_sender_role",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["support_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sender_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_support_messages_conversation_id",
        "support_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_support_messages_conversation_created",
        "support_messages",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_support_messages_conversation_created",
        table_name="support_messages",
    )
    op.drop_index(
        "ix_support_messages_conversation_id",
        table_name="support_messages",
    )
    op.drop_table("support_messages")

    op.drop_index(
        "ix_support_conversations_workspace_updated",
        table_name="support_conversations",
    )
    op.drop_index(
        "ix_support_conversations_payment_request_id",
        table_name="support_conversations",
    )
    op.drop_index(
        "ix_support_conversations_workspace_id",
        table_name="support_conversations",
    )
    op.drop_table("support_conversations")
