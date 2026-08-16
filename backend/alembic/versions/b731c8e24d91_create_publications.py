"""create publications

Revision ID: b731c8e24d91
Revises: 2e7e665d1446
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b731c8e24d91"
down_revision: Union[str, None] = "2e7e665d1446"
branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None
depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "publications",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "content_generation_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "social_account_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "publishing",
                "published",
                "failed",
                "cancelled",
                name="publication_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "platform",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "target_account_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "target_account_name",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "content_snapshot",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "approved_by_user_id",
            sa.UUID(),
            nullable=True,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "publish_attempts",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "provider_post_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "provider_permalink",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "last_error",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "published_at",
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
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brands.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["content_generation_id"],
            ["content_generations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["social_account_id"],
            ["social_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "idempotency_key",
            name=(
                "uq_publications_"
                "workspace_idempotency"
            ),
        ),
    )

    op.create_index(
        op.f(
            "ix_publications_workspace_id"
        ),
        "publications",
        ["workspace_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_publications_brand_id"
        ),
        "publications",
        ["brand_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_publications_content_generation_id"
        ),
        "publications",
        ["content_generation_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_publications_social_account_id"
        ),
        "publications",
        ["social_account_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_publications_created_by_user_id"
        ),
        "publications",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_index(
        op.f(
            "ix_publications_approved_by_user_id"
        ),
        "publications",
        ["approved_by_user_id"],
        unique=False,
    )

    op.create_index(
        "ix_publications_workspace_status",
        "publications",
        [
            "workspace_id",
            "status",
        ],
        unique=False,
    )

    op.create_index(
        "ix_publications_social_status",
        "publications",
        [
            "social_account_id",
            "status",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_publications_social_status",
        table_name="publications",
    )

    op.drop_index(
        "ix_publications_workspace_status",
        table_name="publications",
    )

    op.drop_index(
        op.f(
            "ix_publications_approved_by_user_id"
        ),
        table_name="publications",
    )

    op.drop_index(
        op.f(
            "ix_publications_created_by_user_id"
        ),
        table_name="publications",
    )

    op.drop_index(
        op.f(
            "ix_publications_social_account_id"
        ),
        table_name="publications",
    )

    op.drop_index(
        op.f(
            "ix_publications_content_generation_id"
        ),
        table_name="publications",
    )

    op.drop_index(
        op.f(
            "ix_publications_brand_id"
        ),
        table_name="publications",
    )

    op.drop_index(
        op.f(
            "ix_publications_workspace_id"
        ),
        table_name="publications",
    )

    op.drop_table("publications")

    op.execute(
        "DROP TYPE IF EXISTS publication_status"
    )
