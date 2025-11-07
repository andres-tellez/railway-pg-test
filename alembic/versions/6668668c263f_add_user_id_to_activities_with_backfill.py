"""add user_id to activities with backfill

Revision ID: 6668668c263f
Revises: b48a3cb768f1
Create Date: 2025-09-13 17:23:54.016536

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6668668c263f"
down_revision: Union[str, None] = "b48a3cb768f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.add_column("activities", sa.Column("user_id", postgresql.UUID(), nullable=True))

    op.execute(
        """
        UPDATE activities
        SET user_id = ua.user_id
        FROM user_athletes ua
        WHERE activities.athlete_id = ua.athlete_id
    """
    )

    op.alter_column("activities", "user_id", nullable=False)

    op.create_foreign_key(
        "fk_activities_user_id",
        "activities",
        "user_identity",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema: drop user_id from activities."""
    op.drop_constraint("fk_activities_user_id", "activities", type_="foreignkey")
    op.drop_column("activities", "user_id")
