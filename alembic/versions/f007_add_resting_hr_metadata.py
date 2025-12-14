"""add resting hr source and updated_at to user_profile

Revision ID: f007
Revises: f006
Create Date: 2025-12-12 01:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f007"
down_revision: Union[str, None] = "f006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add resting HR source tracking and updated timestamp to user_profile table."""
    # Add resting_hr_source column (USER | ESTIMATED)
    op.add_column(
        "user_profile",
        sa.Column("resting_hr_source", sa.String(), nullable=True),
    )

    # Add resting_hr_updated_at column
    op.add_column(
        "user_profile",
        sa.Column("resting_hr_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Remove resting HR metadata columns from user_profile table."""
    op.drop_column("user_profile", "resting_hr_updated_at")
    op.drop_column("user_profile", "resting_hr_source")
