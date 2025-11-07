"""create plans table (manual backfill)

Revision ID: 9cba4583175d
Revises: dbb359f494c5
Create Date: 2025-09-12 18:52:41.004106

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9cba4583175d"
down_revision: Union[str, None] = "dbb359f494c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Schema already created manually via raw SQL.
    This migration marks it as applied in version history.
    """
    pass


def downgrade() -> None:
    """Rollback: drop plans table + index."""
    op.drop_index("ix_plans_user_id", table_name="plans")
    op.drop_table("plans")
