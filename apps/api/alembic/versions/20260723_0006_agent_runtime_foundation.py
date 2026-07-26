"""Add message history, context summaries, working state, and governed memory.

Revision ID: 20260723_0006
Revises: 20260722_0005
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_0006"
down_revision: str | None = "20260722_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(
            sa.Column(
                "title_source",
                sa.String(32),
                nullable=False,
                server_default="default",
            )
        )
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_message_at", sa.DateTime(timezone=True)))
        batch.add_column(
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column(
                "session_revision", sa.Integer(), nullable=False, server_default="0"
            )
        )
        batch.add_column(
            sa.Column(
                "parent_session_id",
                sa.String(64),
                sa.ForeignKey("sessions.id", name="fk_sessions_parent_session"),
            )
        )
        batch.add_column(sa.Column("branch_from_message_id", sa.String(64)))
        batch.add_column(
            sa.Column(
                "memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            )
        )
        batch.add_column(
            sa.Column(
                "auto_memory_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column(
                "context_compaction_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch.create_index(
            "ix_sessions_user_last_message", ["user_id", "last_message_at"]
        )
        batch.create_index("ix_sessions_user_archived", ["user_id", "archived_at"])
        batch.create_index("ix_sessions_parent_session_id", ["parent_session_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("visibility", sa.String(32), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "content_data",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "source_task_id", sa.String(64), sa.ForeignKey("tasks.id"), nullable=True
        ),
        sa.Column(
            "reply_to_message_id",
            sa.String(64),
            sa.ForeignKey("conversation_messages.id"),
        ),
        sa.Column(
            "revision_of_message_id",
            sa.String(64),
            sa.ForeignKey("conversation_messages.id"),
        ),
        sa.Column(
            "origin_message_id",
            sa.String(64),
            sa.ForeignKey("conversation_messages.id"),
        ),
        sa.Column(
            "attachment_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "sequence", name="uq_conversation_message_sequence"
        ),
        sa.UniqueConstraint(
            "source_task_id", "role", name="uq_conversation_task_role"
        ),
    )
    op.create_index(
        "ix_conversation_session_sequence",
        "conversation_messages",
        ["session_id", "sequence"],
    )
    op.create_index(
        "ix_conversation_user_created",
        "conversation_messages",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_conversation_reply_to",
        "conversation_messages",
        ["reply_to_message_id"],
    )
    op.create_index(
        "ix_conversation_messages_session_id",
        "conversation_messages",
        ["session_id"],
    )
    op.create_index(
        "ix_conversation_messages_user_id", "conversation_messages", ["user_id"]
    )
    op.create_index(
        "ix_conversation_messages_role", "conversation_messages", ["role"]
    )
    op.create_index(
        "ix_conversation_messages_status", "conversation_messages", ["status"]
    )
    op.create_index(
        "ix_conversation_messages_visibility",
        "conversation_messages",
        ["visibility"],
    )
    op.create_index(
        "ix_conversation_messages_source_task_id",
        "conversation_messages",
        ["source_task_id"],
    )
    op.create_index(
        "ix_conversation_messages_revision_of_message_id",
        "conversation_messages",
        ["revision_of_message_id"],
    )

    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("user_message_id", sa.String(64)))
        batch.add_column(sa.Column("assistant_message_id", sa.String(64)))
        batch.create_index("ix_tasks_user_message_id", ["user_message_id"])
        batch.create_index("ix_tasks_assistant_message_id", ["assistant_message_id"])

    op.create_table(
        "session_working_states",
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column(
            "state_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "session_summaries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("covers_from_sequence", sa.Integer(), nullable=False),
        sa.Column("covers_through_sequence", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column(
            "structured_state",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("source_message_ids", sa.JSON(), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("generation_method", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "version", name="uq_session_summary_version"
        ),
    )
    op.create_index(
        "ix_session_summary_latest",
        "session_summaries",
        ["session_id", "version"],
    )
    op.create_table(
        "memories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("memory_type", sa.String(32), nullable=False, index=True),
        sa.Column("scope", sa.String(32), nullable=False, server_default="global"),
        sa.Column("course_id", sa.String(32)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "content_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "source_session_id",
            sa.String(64),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "source_message_id",
            sa.String(64),
            sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        ),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_memories_user_status_updated",
        "memories",
        ["user_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_memories_user_course", "memories", ["user_id", "course_id"]
    )
    op.create_index(
        "ix_memories_source_session", "memories", ["source_session_id"]
    )
    op.create_index("ix_memories_status", "memories", ["status"])


def downgrade() -> None:
    op.drop_table("memories")
    op.drop_table("session_summaries")
    op.drop_table("session_working_states")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_assistant_message_id")
        batch.drop_index("ix_tasks_user_message_id")
        batch.drop_column("assistant_message_id")
        batch.drop_column("user_message_id")
    op.drop_table("conversation_messages")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_parent_session_id")
        batch.drop_index("ix_sessions_user_archived")
        batch.drop_index("ix_sessions_user_last_message")
        batch.drop_column("context_compaction_enabled")
        batch.drop_column("auto_memory_enabled")
        batch.drop_column("memory_enabled")
        batch.drop_column("branch_from_message_id")
        batch.drop_column("parent_session_id")
        batch.drop_column("session_revision")
        batch.drop_column("message_count")
        batch.drop_column("last_message_at")
        batch.drop_column("archived_at")
        batch.drop_column("title_source")
