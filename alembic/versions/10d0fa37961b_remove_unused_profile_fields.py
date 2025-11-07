"""remove_unused_profile_fields

Revision ID: 10d0fa37961b
Revises: 09759f6633db
Create Date: 2025-10-26 20:32:36.274909

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "10d0fa37961b"
down_revision: Union[str, None] = "09759f6633db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop unused legacy fields from user_profile
    op.drop_column("user_profile", "runner_level")
    op.drop_column("user_profile", "race_history")
    op.drop_column("user_profile", "past_races")
    op.drop_column("user_profile", "main_goal")
    op.drop_column("user_profile", "longest_run")
    op.drop_column("user_profile", "run_preference")


def downgrade() -> None:
    """Downgrade schema."""
    # Add back the legacy fields
    op.add_column(
        "user_profile",
        sa.Column(
            "runner_level",
            sa.Enum("Beginner", "Intermediate", "Expert", name="runnerlevel"),
            nullable=True,
        ),
    )
    op.add_column(
        "user_profile", sa.Column("race_history", sa.Boolean(), nullable=True)
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "past_races",
            sa.ARRAY(
                sa.Enum(
                    "_5K",
                    "_10K",
                    "Half",
                    "Marathon",
                    "Ultra",
                    "NoneYet",
                    name="pastrace",
                )
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "main_goal",
            sa.Enum("Fitness", "Race", "LoseWeight", "Faster", "Other", name="goal"),
            nullable=True,
        ),
    )
    op.add_column("user_profile", sa.Column("longest_run", sa.Float(), nullable=True))
    op.add_column(
        "user_profile",
        sa.Column(
            "run_preference",
            sa.Enum("Distance", "Time", "NonePref", name="runpreference"),
            nullable=True,
        ),
    )
