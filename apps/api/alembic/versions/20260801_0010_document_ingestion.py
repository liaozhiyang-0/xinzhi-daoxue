"""Add document ingestion metadata and extracted chunks.

Revision ID: 20260801_0010
Revises: 20260801_0009
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0010"
down_revision: str | None = "20260801_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "files",
        sa.Column(
            "detected_content_type",
            sa.String(length=128),
            nullable=False,
            server_default="application/octet-stream",
        ),
    )
    op.add_column(
        "files",
        sa.Column(
            "ingestion_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "files", sa.Column("page_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "files", sa.Column("extracted_text", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "files", sa.Column("extraction_metadata", sa.JSON(), nullable=False, server_default="{}")
    )
    op.add_column("files", sa.Column("extraction_error", sa.Text(), nullable=True))
    op.add_column(
        "files",
        sa.Column("extraction_version", sa.String(length=32), nullable=False, server_default="1"),
    )
    op.add_column("files", sa.Column("extraction_started_at", sa.DateTime(timezone=True)))
    op.add_column("files", sa.Column("extraction_completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_files_ingestion_status", "files", ["ingestion_status"])
    op.create_table(
        "file_chunks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("file_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("char_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_ref", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("file_id", "ordinal", name="uq_file_chunks_file_ordinal"),
    )
    op.create_index("ix_file_chunks_file_id", "file_chunks", ["file_id"])
    op.create_index(
        "ix_file_chunks_file_page", "file_chunks", ["file_id", "page_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_file_chunks_file_page", table_name="file_chunks")
    op.drop_index("ix_file_chunks_file_id", table_name="file_chunks")
    op.drop_table("file_chunks")
    op.drop_index("ix_files_ingestion_status", table_name="files")
    for column in (
        "extraction_completed_at",
        "extraction_started_at",
        "extraction_version",
        "extraction_error",
        "extraction_metadata",
        "extracted_text",
        "page_count",
        "ingestion_status",
        "detected_content_type",
    ):
        op.drop_column("files", column)
