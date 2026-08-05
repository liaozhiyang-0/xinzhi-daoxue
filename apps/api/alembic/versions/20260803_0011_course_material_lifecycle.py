"""Add course material identity, version and publication lifecycle.

Revision ID: 20260803_0011
Revises: 20260801_0010
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0011"
down_revision: str | None = "20260801_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("files", sa.Column("course_id", sa.String(length=32)))
    op.add_column("files", sa.Column("material_key", sa.String(length=128)))
    op.add_column("files", sa.Column("material_version", sa.String(length=64)))
    op.add_column(
        "files",
        sa.Column(
            "knowledge_status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column(
        "files",
        sa.Column(
            "knowledge_index_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_indexed",
        ),
    )
    op.add_column("files", sa.Column("knowledge_published_by", sa.String(length=128)))
    op.add_column(
        "files", sa.Column("knowledge_published_at", sa.DateTime(timezone=True))
    )
    op.create_index("ix_files_course_id", "files", ["course_id"])
    op.create_index("ix_files_material_key", "files", ["material_key"])
    op.create_index(
        "ix_files_material_version_scope",
        "files",
        ["course_id", "material_key", "material_version"],
    )
    op.create_index("ix_files_knowledge_status", "files", ["knowledge_status"])


def downgrade() -> None:
    op.drop_index("ix_files_knowledge_status", table_name="files")
    op.drop_index("ix_files_material_version_scope", table_name="files")
    op.drop_index("ix_files_material_key", table_name="files")
    op.drop_index("ix_files_course_id", table_name="files")
    for column in (
        "knowledge_published_at",
        "knowledge_published_by",
        "knowledge_index_status",
        "knowledge_status",
        "material_version",
        "material_key",
        "course_id",
    ):
        op.drop_column("files", column)
