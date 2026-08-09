"""Add durable metadata for the research evidence vector knowledge base.

Revision ID: 20260805_0015
Revises: 20260804_0014
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0015"
down_revision: str | None = "20260804_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("evidence_id", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("content_excerpt", sa.Text(), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("venue", sa.String(length=500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("doi", sa.String(length=256), nullable=False),
        sa.Column("arxiv_id", sa.String(length=128), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("trust_level", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("vector_indexed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", name="uq_research_evidence_id"),
    )
    op.create_index(
        "ix_research_evidence_topic_seen",
        "research_evidence",
        ["topic", "last_seen_at"],
    )
    op.create_index(
        "ix_research_evidence_status_updated",
        "research_evidence",
        ["status", "updated_at"],
    )
    op.create_index(
        "ix_research_evidence_topic",
        "research_evidence",
        ["topic"],
    )
    op.create_index(
        "ix_research_evidence_source_type",
        "research_evidence",
        ["source_type"],
    )
    op.create_index(
        "ix_research_evidence_provider",
        "research_evidence",
        ["provider"],
    )
    op.create_index(
        "ix_research_evidence_status",
        "research_evidence",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_evidence_status", table_name="research_evidence")
    op.drop_index("ix_research_evidence_provider", table_name="research_evidence")
    op.drop_index("ix_research_evidence_source_type", table_name="research_evidence")
    op.drop_index("ix_research_evidence_topic", table_name="research_evidence")
    op.drop_index(
        "ix_research_evidence_status_updated", table_name="research_evidence"
    )
    op.drop_index("ix_research_evidence_topic_seen", table_name="research_evidence")
    op.drop_table("research_evidence")

