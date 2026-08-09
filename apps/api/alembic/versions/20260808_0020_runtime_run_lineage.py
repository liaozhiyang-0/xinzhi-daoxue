"""Persist parent-child Agent Runtime Run lineage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0020"
down_revision: str | None = "20260808_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "parent_run_id",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "parent_node_id",
            sa.String(length=100),
            nullable=False,
            server_default="",
        ),
    )
    op.create_index(
        "ix_agent_runs_parent_run_id", "agent_runs", ["parent_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_runs_parent_run_id", table_name="agent_runs")
    op.drop_column("agent_runs", "parent_node_id")
    op.drop_column("agent_runs", "parent_run_id")
