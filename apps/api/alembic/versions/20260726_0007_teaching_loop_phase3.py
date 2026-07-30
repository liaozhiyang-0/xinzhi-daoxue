"""Add versioned practice attempts and delayed retest plans.

Revision ID: 20260726_0007
Revises: 20260723_0006
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260726_0007"
down_revision: str | None = "20260723_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("practice_attempts") as batch:
        batch.add_column(sa.Column("session_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("task_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("attempt_sequence", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("revision_of_attempt_id", sa.String(64), nullable=True)
        )
        batch.add_column(sa.Column("idempotency_key", sa.String(128), nullable=True))
        batch.add_column(
            sa.Column(
                "steps_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch.add_column(sa.Column("final_answer", sa.Text(), nullable=True))
        batch.add_column(sa.Column("confidence", sa.Float(), nullable=True))
        batch.add_column(
            sa.Column(
                "teaching_mode",
                sa.String(32),
                nullable=False,
                server_default="direct_answer",
            )
        )
        batch.add_column(sa.Column("hint_level_used", sa.String(8), nullable=True))
        batch.add_column(
            sa.Column(
                "full_solution_seen",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("verification_status", sa.String(32), nullable=True))
        batch.add_column(
            sa.Column(
                "verification_report_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch.add_column(
            sa.Column(
                "feedback_uptake_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch.add_column(
            sa.Column(
                "mastery_evidence_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch.add_column(
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.create_foreign_key(
            "fk_practice_attempt_session",
            "sessions",
            ["session_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_foreign_key(
            "fk_practice_attempt_task", "tasks", ["task_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_practice_attempt_revision",
            "practice_attempts",
            ["revision_of_attempt_id"],
            ["id"],
        )
        batch.create_unique_constraint(
            "uq_practice_attempt_source_sequence",
            ["source_task_id", "attempt_sequence"],
        )
        batch.create_unique_constraint(
            "uq_practice_attempt_user_idempotency",
            ["user_id", "idempotency_key"],
        )
        batch.create_index(
            "ix_practice_attempt_user_created", ["user_id", "created_at"]
        )
        batch.create_index(
            "ix_practice_attempt_session_sequence",
            ["session_id", "attempt_sequence"],
        )
        batch.create_index(
            "ix_practice_attempt_source_sequence",
            ["source_task_id", "attempt_sequence"],
        )
        batch.create_index("ix_practice_attempt_revision", ["revision_of_attempt_id"])

    op.create_table(
        "retest_plans",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("skill_id", sa.String(255), nullable=False),
        sa.Column(
            "source_task_id",
            sa.String(64),
            sa.ForeignKey("tasks.id"),
            nullable=False,
        ),
        sa.Column(
            "source_attempt_id",
            sa.String(64),
            sa.ForeignKey("practice_attempts.id"),
            nullable=True,
        ),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("generated_problem_id", sa.String(64), nullable=True),
        sa.Column(
            "completed_task_id",
            sa.String(64),
            sa.ForeignKey("tasks.id"),
            nullable=True,
        ),
        sa.Column("result", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "user_id",
            "skill_id",
            "source_task_id",
            "interval_days",
            name="uq_retest_plan_source_interval",
        ),
    )
    op.create_index("ix_retest_plans_user_id", "retest_plans", ["user_id"])
    op.create_index(
        "ix_retest_user_status_due",
        "retest_plans",
        ["user_id", "status", "due_at"],
    )
    op.create_index("ix_retest_skill_due", "retest_plans", ["skill_id", "due_at"])
    op.create_index("ix_retest_source_task", "retest_plans", ["source_task_id"])


def downgrade() -> None:
    op.drop_table("retest_plans")
    with op.batch_alter_table("practice_attempts") as batch:
        batch.drop_index("ix_practice_attempt_revision")
        batch.drop_index("ix_practice_attempt_source_sequence")
        batch.drop_index("ix_practice_attempt_session_sequence")
        batch.drop_index("ix_practice_attempt_user_created")
        batch.drop_constraint("uq_practice_attempt_user_idempotency", type_="unique")
        batch.drop_constraint("uq_practice_attempt_source_sequence", type_="unique")
        batch.drop_constraint("fk_practice_attempt_revision", type_="foreignkey")
        batch.drop_constraint("fk_practice_attempt_task", type_="foreignkey")
        batch.drop_constraint("fk_practice_attempt_session", type_="foreignkey")
        batch.drop_column("updated_at")
        batch.drop_column("submitted_at")
        batch.drop_column("mastery_evidence_json")
        batch.drop_column("feedback_uptake_json")
        batch.drop_column("verification_report_json")
        batch.drop_column("verification_status")
        batch.drop_column("full_solution_seen")
        batch.drop_column("hint_level_used")
        batch.drop_column("teaching_mode")
        batch.drop_column("confidence")
        batch.drop_column("final_answer")
        batch.drop_column("steps_json")
        batch.drop_column("idempotency_key")
        batch.drop_column("revision_of_attempt_id")
        batch.drop_column("attempt_sequence")
        batch.drop_column("task_id")
        batch.drop_column("session_id")
