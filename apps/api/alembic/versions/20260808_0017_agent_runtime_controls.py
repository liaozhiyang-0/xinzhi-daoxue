"""Add durable Runtime control requests for pause/resume/approval."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0017"
down_revision: str | None = "20260808_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "control_request",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "control_data",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "control_data")
    op.drop_column("agent_runs", "control_request")
