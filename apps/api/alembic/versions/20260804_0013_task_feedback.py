"""Add explicit task feedback and version snapshot storage.

Revision ID: 20260804_0013
Revises: 20260804_0012
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0013"
down_revision: str | None = "20260804_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_feedback",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("user_role", sa.String(length=32), nullable=False),
        sa.Column("course_id", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("agent_version", sa.String(length=32), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("rag_version", sa.String(length=128), nullable=True),
        sa.Column("retrieval_mode", sa.String(length=64), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=True),
        sa.Column("satisfaction", sa.String(length=32), nullable=True),
        sa.Column("problem_type", sa.String(length=64), nullable=True),
        sa.Column(
            "manual_review_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("citation_coverage", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_feedback_task_user"),
    )
    op.create_index(
        "ix_task_feedback_created_course",
        "task_feedback",
        ["created_at", "course_id"],
    )
    op.create_index(
        "ix_task_feedback_user_created", "task_feedback", ["user_id", "created_at"]
    )
    op.create_index("ix_task_feedback_task_id", "task_feedback", ["task_id"])
    op.create_index("ix_task_feedback_user_id", "task_feedback", ["user_id"])
    op.create_index("ix_task_feedback_course_id", "task_feedback", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_task_feedback_course_id", table_name="task_feedback")
    op.drop_index("ix_task_feedback_user_id", table_name="task_feedback")
    op.drop_index("ix_task_feedback_task_id", table_name="task_feedback")
    op.drop_index("ix_task_feedback_user_created", table_name="task_feedback")
    op.drop_index("ix_task_feedback_created_course", table_name="task_feedback")
    op.drop_table("task_feedback")
