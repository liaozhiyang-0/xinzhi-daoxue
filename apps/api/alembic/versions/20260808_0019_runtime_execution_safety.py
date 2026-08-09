"""Persist Runtime execution keys and effect recovery state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0019"
down_revision: str | None = "20260808_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_run_nodes",
        sa.Column(
            "execution_key",
            sa.String(length=240),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "agent_run_nodes",
        sa.Column(
            "effect_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_started",
        ),
    )
    op.create_index(
        "ix_agent_run_nodes_run_effect_status",
        "agent_run_nodes",
        ["run_id", "effect_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_run_nodes_run_effect_status",
        table_name="agent_run_nodes",
    )
    op.drop_column("agent_run_nodes", "effect_status")
    op.drop_column("agent_run_nodes", "execution_key")
