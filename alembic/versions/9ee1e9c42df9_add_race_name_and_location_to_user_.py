"""add_race_name_and_location_to_user_profile

Revision ID: 9ee1e9c42df9
Revises: f003
Create Date: 2025-10-25 08:53:52.239502

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9ee1e9c42df9"
down_revision: Union[str, None] = "f003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add race_name and race_location to user_profile."""
    op.add_column("user_profile", sa.Column("race_name", sa.String(), nullable=True))
    op.add_column(
        "user_profile", sa.Column("race_location", sa.String(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema: remove race_name and race_location from user_profile."""
    op.drop_column("user_profile", "race_location")
    op.drop_column("user_profile", "race_name")
