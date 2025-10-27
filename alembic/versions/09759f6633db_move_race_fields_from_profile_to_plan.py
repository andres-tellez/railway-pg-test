"""move_race_fields_from_profile_to_plan

Revision ID: 09759f6633db
Revises: 3ac303538a7d
Create Date: 2025-10-26 19:17:37.496356

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "09759f6633db"
down_revision: Union[str, None] = "3ac303538a7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema: move race fields from user_profile to plans.
    - Add race_name and race_location to plans table
    - Copy race data from user_profile to plans (if plans exist)
    - Drop race fields from user_profile
    """

    # 1. Add race_name and race_location columns to plans
    op.add_column("plans", sa.Column("race_name", sa.String(), nullable=True))
    op.add_column("plans", sa.Column("race_location", sa.String(), nullable=True))

    # 2. Copy race data from user_profile to plans
    # For each user with a profile, update their plans with race info
    op.execute(
        """
        UPDATE plans
        SET race_name = up.race_name,
            race_location = up.race_location
        FROM user_profile up
        WHERE plans.user_id::text = up.user_id::text
        AND up.race_name IS NOT NULL
    """
    )

    # 3. Drop race fields from user_profile
    op.drop_column("user_profile", "race_location")
    op.drop_column("user_profile", "race_name")
    op.drop_column("user_profile", "race_distance")
    op.drop_column("user_profile", "race_date")


def downgrade() -> None:
    """
    Downgrade schema: move race fields back from plans to user_profile.
    """

    # 1. Add race fields back to user_profile
    op.add_column("user_profile", sa.Column("race_date", sa.String(), nullable=True))
    op.add_column(
        "user_profile", sa.Column("race_distance", sa.String(), nullable=True)
    )
    op.add_column("user_profile", sa.Column("race_name", sa.String(), nullable=True))
    op.add_column(
        "user_profile", sa.Column("race_location", sa.String(), nullable=True)
    )

    # 2. Copy race data from plans back to user_profile
    op.execute(
        """
        UPDATE user_profile up
        SET race_name = p.race_name,
            race_location = p.race_location,
            race_date = p.race_date::text,
            race_distance = p.race_distance
        FROM plans p
        WHERE up.user_id = p.user_id::text
        AND p.is_active = true
        AND p.race_name IS NOT NULL
    """
    )

    # 3. Drop race_name and race_location from plans
    op.drop_column("plans", "race_location")
    op.drop_column("plans", "race_name")
