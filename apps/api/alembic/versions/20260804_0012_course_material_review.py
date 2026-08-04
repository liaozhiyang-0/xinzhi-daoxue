"""Add course material teacher review lifecycle fields.

Revision ID: 20260804_0012
Revises: 20260803_0011
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0012"
down_revision: str | None = "20260803_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column(
            "material_review_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.add_column("files", sa.Column("material_reviewed_by", sa.String(length=128)))
    op.add_column(
        "files", sa.Column("material_reviewed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "files", sa.Column("material_review_note", sa.String(length=1000))
    )
    op.create_index(
        "ix_files_material_review_status", "files", ["material_review_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_files_material_review_status", table_name="files")
    for column in (
        "material_review_note",
        "material_reviewed_at",
        "material_reviewed_by",
        "material_review_status",
    ):
        op.drop_column("files", column)
