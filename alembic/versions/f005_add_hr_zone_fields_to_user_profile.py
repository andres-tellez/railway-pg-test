"""add hr zone fields to user_profile

Revision ID: f005
Revises: f004
Create Date: 2025-12-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f005"
down_revision: Union[str, None] = "f004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add HR zone calculation fields to user_profile table."""
    # Add resting_hr column
    op.add_column("user_profile", sa.Column("resting_hr", sa.Integer(), nullable=True))

    # Add max_hr_source column
    op.add_column(
        "user_profile", sa.Column("max_hr_source", sa.String(), nullable=True)
    )

    # Add hrmax_calculated_at column
    op.add_column(
        "user_profile",
        sa.Column("hrmax_calculated_at", sa.DateTime(), nullable=True),
    )

    # Add hrmax_confidence column
    op.add_column(
        "user_profile", sa.Column("hrmax_confidence", sa.String(), nullable=True)
    )

    # Add hrmax_activity_count column
    op.add_column(
        "user_profile", sa.Column("hrmax_activity_count", sa.Integer(), nullable=True)
    )

    # Add last_hrmax_activity_id column
    op.add_column(
        "user_profile",
        sa.Column("last_hrmax_activity_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    """Remove HR zone calculation fields from user_profile table."""
    op.drop_column("user_profile", "last_hrmax_activity_id")
    op.drop_column("user_profile", "hrmax_activity_count")
    op.drop_column("user_profile", "hrmax_confidence")
    op.drop_column("user_profile", "hrmax_calculated_at")
    op.drop_column("user_profile", "max_hr_source")
    op.drop_column("user_profile", "resting_hr")
