"""dual max HR: manual vs auto + active selector

Revision ID: f011
Revises: f010
Create Date: 2026-04-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f011"
down_revision: Union[str, None] = "f010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("max_hr_manual", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_profile",
        sa.Column("max_hr_auto", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_profile",
        sa.Column("max_hr_active", sa.String(length=16), nullable=True),
    )

    # Backfill from legacy max_hr + max_hr_source
    op.execute(
        """
        UPDATE user_profile SET
          max_hr_manual = CASE
            WHEN max_hr_source IN ('USER', 'STRAVA') THEN max_hr
            WHEN max_hr IS NOT NULL AND (max_hr_source IS NULL OR max_hr_source = '') THEN max_hr
            ELSE NULL
          END,
          max_hr_auto = CASE
            WHEN max_hr_source = 'AUTO' THEN max_hr
            ELSE NULL
          END,
          max_hr_active = CASE
            WHEN max_hr_source = 'AUTO' THEN 'auto'
            WHEN max_hr IS NOT NULL THEN 'manual'
            ELSE NULL
          END
        """
    )

    op.drop_column("user_profile", "max_hr")
    op.drop_column("user_profile", "max_hr_source")


def downgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("max_hr", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_profile",
        sa.Column("max_hr_source", sa.String(), nullable=True),
    )

    op.execute(
        """
        UPDATE user_profile SET
          max_hr = CASE
            WHEN max_hr_active = 'auto' AND max_hr_auto IS NOT NULL THEN max_hr_auto
            WHEN max_hr_manual IS NOT NULL THEN max_hr_manual
            WHEN max_hr_auto IS NOT NULL THEN max_hr_auto
            ELSE NULL
          END,
          max_hr_source = CASE
            WHEN max_hr_active = 'auto' THEN 'AUTO'
            WHEN max_hr_manual IS NOT NULL THEN 'USER'
            WHEN max_hr_auto IS NOT NULL THEN 'AUTO'
            ELSE NULL
          END
        """
    )

    op.drop_column("user_profile", "max_hr_active")
    op.drop_column("user_profile", "max_hr_auto")
    op.drop_column("user_profile", "max_hr_manual")
