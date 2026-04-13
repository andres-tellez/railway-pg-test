"""Detach activities.user_id when athlete_id != linked user_athletes row.

Phase 2 data integrity: one app user must map to one Strava athlete (user_athletes).
Rows where activities.user_id is set but activities.athlete_id differs from that
user's linked athlete_id are legacy / wrong-account linkage; clear user_id so
they are no longer treated as the app's runs (Strava rows remain for audit).

Revision ID: f013
Revises: f012
Create Date: 2026-04-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "f013"
down_revision: Union[str, None] = "f012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Required so we can clear ownership on mismatched rows (historically NOT NULL).
    op.alter_column("activities", "user_id", nullable=True)

    # Compare as text so this works whether columns are uuid or varchar (uuid = text errors otherwise).
    op.execute(
        """
        UPDATE activities AS a
        SET user_id = NULL
        FROM user_athletes AS ua
        WHERE a.user_id IS NOT NULL
          AND ua.user_id::text = a.user_id::text
          AND a.athlete_id IS DISTINCT FROM ua.athlete_id
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    n = bind.execute(
        text("SELECT COUNT(*) FROM activities WHERE user_id IS NULL")
    ).scalar()
    if n and int(n) > 0:
        raise RuntimeError(
            "Cannot downgrade f013: activities.user_id has NULL rows. "
            "Restore from backup or repopulate user_id before re-applying NOT NULL."
        )
    op.alter_column("activities", "user_id", nullable=False)
