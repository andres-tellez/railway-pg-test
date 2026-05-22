"""Drop unused last_hrmax_activity_id from user_profile

Revision ID: f018
Revises: f017

The column was never populated by application code (only cleared). Matches DBs where
column was dropped manually; uses IF EXISTS for idempotency.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f018"
down_revision: Union[str, None] = "f017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_profile DROP COLUMN IF EXISTS last_hrmax_activity_id")


def downgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("last_hrmax_activity_id", sa.BigInteger(), nullable=True),
    )
