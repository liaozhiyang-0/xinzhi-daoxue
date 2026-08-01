"""Add account and opaque authentication session storage.

Revision ID: 20260801_0008
Revises: 20260726_0007
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0008"
down_revision: str | None = "20260726_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("login", sa.String(length=255), nullable=False),
        sa.Column("login_normalized", sa.String(length=255), nullable=False),
        sa.Column(
            "display_name", sa.String(length=255), nullable=False, server_default=""
        ),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column(
            "role", sa.String(length=32), nullable=False, server_default="student"
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("login_normalized", name="uq_accounts_login_normalized"),
    )
    op.create_index("ix_accounts_login_normalized", "accounts", ["login_normalized"])
    op.create_index("ix_accounts_status_created", "accounts", ["status", "created_at"])
    op.create_index("ix_accounts_role", "accounts", ["role"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("access_token_hash", name="uq_auth_sessions_access_hash"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_hash"),
    )
    op.create_index(
        "ix_auth_sessions_account_active", "auth_sessions", ["account_id", "revoked_at"]
    )
    op.create_index(
        "ix_auth_sessions_access_expires", "auth_sessions", ["access_expires_at"]
    )
    op.create_index(
        "ix_auth_sessions_refresh_expires", "auth_sessions", ["refresh_expires_at"]
    )

    with op.batch_alter_table("files") as batch:
        batch.add_column(
            sa.Column("owner_user_id", sa.String(length=128), nullable=True)
        )
        batch.create_index("ix_files_owner_user_id", ["owner_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("files") as batch:
        batch.drop_index("ix_files_owner_user_id")
        batch.drop_column("owner_user_id")
    op.drop_index("ix_auth_sessions_refresh_expires", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_access_expires", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_account_active", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_accounts_role", table_name="accounts")
    op.drop_index("ix_accounts_status_created", table_name="accounts")
    op.drop_index("ix_accounts_login_normalized", table_name="accounts")
    op.drop_table("accounts")
