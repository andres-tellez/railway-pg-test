"""Add plans.context_snapshot (7a8b workout-metadata branch).

Revision ID: 7a8b9c0d1e3
Revises: 7a8b9c0d1e2f
Create Date: 2026-04-30

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7a8b9c0d1e3"
down_revision: Union[str, None] = "7a8b9c0d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "context_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Optional reasoning snapshot from plan generation "
                "(validation spine, decision_trace, metadata)."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("plans", "context_snapshot")
