"""Add lightweight student session context and temporary upload metadata.

Revision ID: 20260718_0004
Revises: 20260717_0003
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0004"
down_revision: str | None = "20260717_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(
            sa.Column(
                "context_data",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
    with op.batch_alter_table("files") as batch:
        batch.add_column(
            sa.Column(
                "purpose",
                sa.String(64),
                nullable=False,
                server_default="generic",
            )
        )
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    with op.batch_alter_table("files") as batch:
        batch.drop_column("expires_at")
        batch.drop_column("purpose")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("context_data")
