"""Persist Runtime node target identifiers for replay and diagnostics."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0018"
down_revision: str | None = "20260808_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_run_nodes",
        sa.Column("target_id", sa.String(length=160), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("agent_run_nodes", "target_id")
