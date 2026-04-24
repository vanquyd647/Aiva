"""Add provider secrets table for encrypted AI keys

Revision ID: 20260424_000004
Revises: 20260424_000003
Create Date: 2026-04-24 00:00:04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260424_000004"
down_revision = "20260424_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("rotated_reason", sa.String(length=255), nullable=True),
        sa.Column("rotated_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "rotated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["rotated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_secrets_id", "provider_secrets", ["id"], unique=False)
    op.create_index("ix_provider_secrets_provider", "provider_secrets", ["provider"], unique=False)
    op.create_index("ix_provider_secrets_status", "provider_secrets", ["status"], unique=False)
    op.create_index(
        "ix_provider_secrets_secret_fingerprint",
        "provider_secrets",
        ["secret_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_provider_secrets_rotated_by_user_id",
        "provider_secrets",
        ["rotated_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_provider_secrets_rotated_at",
        "provider_secrets",
        ["rotated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_secrets_rotated_at", table_name="provider_secrets")
    op.drop_index("ix_provider_secrets_rotated_by_user_id", table_name="provider_secrets")
    op.drop_index("ix_provider_secrets_secret_fingerprint", table_name="provider_secrets")
    op.drop_index("ix_provider_secrets_status", table_name="provider_secrets")
    op.drop_index("ix_provider_secrets_provider", table_name="provider_secrets")
    op.drop_index("ix_provider_secrets_id", table_name="provider_secrets")
    op.drop_table("provider_secrets")
