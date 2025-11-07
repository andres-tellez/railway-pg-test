"""add_race_metadata_to_plans

Revision ID: cc57a44b0d46
Revises: ac380280e363
Create Date: 2025-10-31 13:06:08.023732

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "cc57a44b0d46"
down_revision: Union[str, None] = "ac380280e363"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add race_metadata JSONB column to plans table."""
    op.add_column(
        "plans",
        sa.Column(
            "race_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Race metadata including terrain, elevation gain, course type, etc.",
        ),
    )


def downgrade() -> None:
    """Remove race_metadata column from plans table."""
    op.drop_column("plans", "race_metadata")
