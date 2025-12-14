"""add strava premium status to user_athletes

Revision ID: f006
Revises: f005
Create Date: 2025-12-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f006"
down_revision: Union[str, None] = "f005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Strava premium/Summit subscription status columns to user_athletes table."""
    # Add has_strava_premium column
    op.add_column(
        "user_athletes", sa.Column("has_strava_premium", sa.Boolean(), nullable=True)
    )

    # Add strava_premium_checked_at column
    op.add_column(
        "user_athletes",
        sa.Column(
            "strava_premium_checked_at", sa.DateTime(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    """Remove Strava premium status columns from user_athletes table."""
    op.drop_column("user_athletes", "strava_premium_checked_at")
    op.drop_column("user_athletes", "has_strava_premium")
