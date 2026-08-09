"""Add durable Agent Runtime run, node, and checkpoint state.

Revision ID: 20260808_0016
Revises: 20260805_0015
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0016"
down_revision: str | None = "20260805_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "run_kind", sa.String(length=32), nullable=False, server_default="agent"
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("plan_id", sa.String(length=120), nullable=False, server_default=""),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "plan_version", sa.String(length=32), nullable=False, server_default="1"
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("iteration", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "budget_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "terminal_reason",
            sa.String(length=256),
            nullable=False,
            server_default="",
        ),
    )

    op.create_table(
        "agent_run_nodes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("node_id", sa.String(length=100), nullable=False),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        sa.Column("handler_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("input_artifact_ids", sa.JSON(), nullable=False),
        sa.Column("output_artifact_ids", sa.JSON(), nullable=False),
        sa.Column("observation_data", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "node_id", name="uq_agent_run_nodes_run_node"),
    )
    op.create_index(
        "ix_agent_run_nodes_run_id", "agent_run_nodes", ["run_id"]
    )
    op.create_index(
        "ix_agent_run_nodes_status", "agent_run_nodes", ["status"]
    )
    op.create_index(
        "ix_agent_run_nodes_run_status",
        "agent_run_nodes",
        ["run_id", "status"],
    )

    op.create_table(
        "agent_checkpoints",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("state_data", sa.JSON(), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "sequence", name="uq_agent_checkpoints_run_sequence"
        ),
    )
    op.create_index(
        "ix_agent_checkpoints_run_id", "agent_checkpoints", ["run_id"]
    )
    op.create_index(
        "ix_agent_checkpoints_run_created",
        "agent_checkpoints",
        ["run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_checkpoints_run_created", table_name="agent_checkpoints"
    )
    op.drop_index("ix_agent_checkpoints_run_id", table_name="agent_checkpoints")
    op.drop_table("agent_checkpoints")

    op.drop_index("ix_agent_run_nodes_run_status", table_name="agent_run_nodes")
    op.drop_index("ix_agent_run_nodes_status", table_name="agent_run_nodes")
    op.drop_index("ix_agent_run_nodes_run_id", table_name="agent_run_nodes")
    op.drop_table("agent_run_nodes")

    op.drop_column("agent_runs", "terminal_reason")
    op.drop_column("agent_runs", "state_version")
    op.drop_column("agent_runs", "budget_data")
    op.drop_column("agent_runs", "iteration")
    op.drop_column("agent_runs", "plan_version")
    op.drop_column("agent_runs", "plan_id")
    op.drop_column("agent_runs", "run_kind")
