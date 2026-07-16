"""Add ordered events and task lifecycle fields.

Revision ID: 20260717_0002
Revises: 20260716_0001
Create Date: 2026-07-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260717_0002"
down_revision: str | None = "20260716_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("parent_task_id", sa.String(64), nullable=True))
        batch.add_column(
            sa.Column(
                "attempt", sa.Integer(), nullable=False, server_default=sa.text("1")
            )
        )
        batch.add_column(
            sa.Column(
                "cancellation_requested",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
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
            "fk_tasks_parent_task_id", "tasks", ["parent_task_id"], ["id"]
        )
        batch.create_index("ix_tasks_parent_task_id", ["parent_task_id"])
        batch.create_index("ix_tasks_status_created_at", ["status", "created_at"])

    with op.batch_alter_table("files") as batch:
        batch.add_column(
            sa.Column(
                "checksum_sha256",
                sa.String(64),
                nullable=False,
                server_default="",
            )
        )
        batch.create_index("ix_files_checksum_sha256", ["checksum_sha256"])

    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
        )

    with op.batch_alter_table("task_events") as batch:
        batch.add_column(
            sa.Column(
                "sequence", sa.Integer(), nullable=False, server_default=sa.text("0")
            )
        )

    connection = op.get_bind()
    task_ids = [
        row[0]
        for row in connection.execute(
            sa.text("SELECT DISTINCT task_id FROM task_events")
        ).fetchall()
    ]
    for task_id in task_ids:
        rows = connection.execute(
            sa.text(
                "SELECT id FROM task_events WHERE task_id = :task_id "
                "ORDER BY created_at, id"
            ),
            {"task_id": task_id},
        ).fetchall()
        for sequence, row in enumerate(rows, start=1):
            connection.execute(
                sa.text("UPDATE task_events SET sequence = :sequence WHERE id = :id"),
                {"sequence": sequence, "id": row[0]},
            )

    with op.batch_alter_table("task_events") as batch:
        batch.create_unique_constraint(
            "uq_task_events_sequence", ["task_id", "sequence"]
        )
        batch.create_index(
            "ix_task_events_task_sequence", ["task_id", "sequence"]
        )


def downgrade() -> None:
    with op.batch_alter_table("task_events") as batch:
        batch.drop_index("ix_task_events_task_sequence")
        batch.drop_constraint("uq_task_events_sequence", type_="unique")
        batch.drop_column("sequence")

    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_column("completed_at")
        batch.drop_column("started_at")

    with op.batch_alter_table("files") as batch:
        batch.drop_index("ix_files_checksum_sha256")
        batch.drop_column("checksum_sha256")

    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_status_created_at")
        batch.drop_index("ix_tasks_parent_task_id")
        batch.drop_constraint("fk_tasks_parent_task_id", type_="foreignkey")
        batch.drop_column("updated_at")
        batch.drop_column("cancellation_requested")
        batch.drop_column("attempt")
        batch.drop_column("parent_task_id")
