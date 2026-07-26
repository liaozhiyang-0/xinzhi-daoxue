"""Add learning loop and task execution reliability fields.

Revision ID: 20260722_0005
Revises: 20260718_0004
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0005"
down_revision: str | None = "20260718_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("idempotency_key", sa.String(128)))
        batch.add_column(
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3")
        )
        batch.add_column(sa.Column("execution_owner", sa.String(128)))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("cancel_requested_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("failure_category", sa.String(64)))
        batch.create_index("ix_tasks_idempotency_key", ["idempotency_key"])
        batch.create_unique_constraint(
            "uq_tasks_user_idempotency", ["user_id", "idempotency_key"]
        )
    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(sa.Column("trace_id", sa.String(64)))
        batch.add_column(
            sa.Column(
                "metrics_data",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch.create_index("ix_agent_runs_trace_id", ["trace_id"])

    op.create_table(
        "learner_knowledge_states",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("course_id", sa.String(32), nullable=False, index=True),
        sa.Column("knowledge_point", sa.String(255), nullable=False, index=True),
        sa.Column("mastery_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incorrect_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "course_id", "knowledge_point", name="uq_learner_point"
        ),
    )
    op.create_table(
        "wrong_answer_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "source_task_id",
            sa.String(64),
            sa.ForeignKey("tasks.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("course_id", sa.String(32), nullable=False, index=True),
        sa.Column("chapter", sa.String(255)),
        sa.Column("knowledge_points", sa.JSON(), nullable=False),
        sa.Column("problem_summary", sa.Text(), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("error_types", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.JSON(), nullable=False),
        sa.Column("mastery_before", sa.Float(), nullable=False),
        sa.Column("mastery_after", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "practice_attempts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "source_task_id",
            sa.String(64),
            sa.ForeignKey("tasks.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("course_id", sa.String(32), nullable=False, index=True),
        sa.Column("problem", sa.JSON(), nullable=False),
        sa.Column("reference_answer", sa.JSON(), nullable=False),
        sa.Column("student_answer", sa.Text(), nullable=False),
        sa.Column("review_result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "learning_interactions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "source_task_id",
            sa.String(64),
            sa.ForeignKey("tasks.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_learning_action_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("learning_interactions")
    op.drop_table("practice_attempts")
    op.drop_table("wrong_answer_records")
    op.drop_table("learner_knowledge_states")
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_index("ix_agent_runs_trace_id")
        batch.drop_column("metrics_data")
        batch.drop_column("trace_id")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_constraint("uq_tasks_user_idempotency", type_="unique")
        batch.drop_index("ix_tasks_idempotency_key")
        batch.drop_column("failure_category")
        batch.drop_column("cancel_requested_at")
        batch.drop_column("heartbeat_at")
        batch.drop_column("lease_expires_at")
        batch.drop_column("execution_owner")
        batch.drop_column("max_attempts")
        batch.drop_column("idempotency_key")
