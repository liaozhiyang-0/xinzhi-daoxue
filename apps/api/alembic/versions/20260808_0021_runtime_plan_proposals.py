"""Persist adaptive Runtime plan proposals and review decisions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0021"
down_revision: str | None = "20260808_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_plan_proposals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("base_iteration", sa.Integer(), nullable=False),
        sa.Column("target_iteration", sa.Integer(), nullable=False),
        sa.Column("base_state_version", sa.Integer(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("base_plan_id", sa.String(length=120), nullable=False),
        sa.Column("base_plan_version", sa.String(length=32), nullable=False),
        sa.Column("proposed_plan_data", sa.JSON(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("affected_node_ids", sa.JSON(), nullable=False),
        sa.Column("budget_impact_data", sa.JSON(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("decision_reason", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_plan_proposals_run_id",
        "agent_plan_proposals",
        ["run_id"],
    )
    op.create_index(
        "ix_agent_plan_proposals_task_id",
        "agent_plan_proposals",
        ["task_id"],
    )
    op.create_index(
        "ix_agent_plan_proposals_status",
        "agent_plan_proposals",
        ["status"],
    )
    op.create_index(
        "ix_agent_plan_proposals_run_status",
        "agent_plan_proposals",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_agent_plan_proposals_task_created",
        "agent_plan_proposals",
        ["task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_plan_proposals_task_created",
        table_name="agent_plan_proposals",
    )
    op.drop_index(
        "ix_agent_plan_proposals_run_status",
        table_name="agent_plan_proposals",
    )
    op.drop_index(
        "ix_agent_plan_proposals_status",
        table_name="agent_plan_proposals",
    )
    op.drop_index(
        "ix_agent_plan_proposals_task_id",
        table_name="agent_plan_proposals",
    )
    op.drop_index(
        "ix_agent_plan_proposals_run_id",
        table_name="agent_plan_proposals",
    )
    op.drop_table("agent_plan_proposals")
