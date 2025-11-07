"""add_is_active_to_plans

Revision ID: 3ac303538a7d
Revises: 9ee1e9c42df9
Create Date: 2025-10-25 08:59:16.781574

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3ac303538a7d"
down_revision: Union[str, None] = "9ee1e9c42df9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add is_active flag to plans table."""
    # Column already exists, just mark migration as applied
    # The column was added manually to the database
    pass


def downgrade() -> None:
    """Downgrade schema: remove is_active from plans."""
    op.drop_column("plans", "is_active")
