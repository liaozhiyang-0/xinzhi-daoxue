"""Add the single governed Experience Memory record store.

This is an additive migration.  It deliberately does not alter the existing
``memories`` table or create separate success/failure/strategy tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0022"
down_revision: str | None = "20260808_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experience_records",
        sa.Column("experience_id", sa.String(length=80), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("experience_type", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("scope_owner_id", sa.String(length=128), nullable=True),
        sa.Column("course_id", sa.String(length=32), nullable=True),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("skill_ids", sa.JSON(), nullable=False),
        sa.Column("skill_versions", sa.JSON(), nullable=False),
        sa.Column("tool_ids", sa.JSON(), nullable=False),
        sa.Column("tool_versions", sa.JSON(), nullable=False),
        sa.Column("planner_version", sa.String(length=64), nullable=False),
        sa.Column("plan_signature", sa.String(length=128), nullable=False),
        sa.Column("model_versions", sa.JSON(), nullable=False),
        sa.Column("input_feature_summary", sa.JSON(), nullable=False),
        sa.Column("problem_type", sa.String(length=128), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("strategy_summary", sa.Text(), nullable=False),
        sa.Column("failure_stage", sa.String(length=128), nullable=False),
        sa.Column("error_codes", sa.JSON(), nullable=False),
        sa.Column("verification_result", sa.JSON(), nullable=False),
        sa.Column("reflection_result", sa.JSON(), nullable=False),
        sa.Column("outcome_metrics", sa.JSON(), nullable=False),
        sa.Column("evidence_level", sa.String(length=64), nullable=False),
        sa.Column("source_trace_ids", sa.JSON(), nullable=False),
        sa.Column("source_run_ids", sa.JSON(), nullable=False),
        sa.Column("source_eval_ids", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes", sa.String(length=80), nullable=True),
        sa.Column("conflicts_with", sa.JSON(), nullable=False),
        sa.Column("privacy_class", sa.String(length=64), nullable=False),
        sa.Column("redaction_status", sa.String(length=32), nullable=False),
        sa.Column("promotion_provenance", sa.JSON(), nullable=False),
        sa.Column("applicability", sa.JSON(), nullable=False),
        sa.Column("counterexamples", sa.JSON(), nullable=False),
        sa.Column("failure_rate", sa.Float(), nullable=True),
        sa.Column("forgotten_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("experience_id"),
    )
    op.create_index(
        "ix_experience_records_lifecycle_scope",
        "experience_records",
        ["lifecycle_status", "scope"],
    )
    op.create_index(
        "ix_experience_records_course_capability",
        "experience_records",
        ["course_id", "capability_id"],
    )
    op.create_index(
        "ix_experience_records_owner_lifecycle",
        "experience_records",
        ["scope_owner_id", "lifecycle_status"],
    )
    op.create_index(
        "ix_experience_records_expiry",
        "experience_records",
        ["lifecycle_status", "expires_at"],
    )
    op.create_index(
        "ix_experience_records_experience_type",
        "experience_records",
        ["experience_type"],
    )
    op.create_index(
        "ix_experience_records_evidence_level",
        "experience_records",
        ["evidence_level"],
    )
    op.create_index(
        "ix_experience_records_course_id",
        "experience_records",
        ["course_id"],
    )
    op.create_index(
        "ix_experience_records_capability_id",
        "experience_records",
        ["capability_id"],
    )
    op.create_index(
        "ix_experience_records_scope_owner_id",
        "experience_records",
        ["scope_owner_id"],
    )
    op.create_index(
        "ix_experience_records_supersedes",
        "experience_records",
        ["supersedes"],
    )


def downgrade() -> None:
    for name in (
        "ix_experience_records_supersedes",
        "ix_experience_records_scope_owner_id",
        "ix_experience_records_capability_id",
        "ix_experience_records_course_id",
        "ix_experience_records_evidence_level",
        "ix_experience_records_experience_type",
        "ix_experience_records_expiry",
        "ix_experience_records_owner_lifecycle",
        "ix_experience_records_course_capability",
        "ix_experience_records_lifecycle_scope",
    ):
        op.drop_index(name, table_name="experience_records")
    op.drop_table("experience_records")
