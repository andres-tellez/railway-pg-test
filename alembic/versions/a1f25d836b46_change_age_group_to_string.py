"""change_age_group_to_string

Revision ID: a1f25d836b46
Revises: 10d0fa37961b
Create Date: 2025-10-27 09:11:55.900711

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f25d836b46"
down_revision: Union[str, None] = "10d0fa37961b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: change age_group from enum to string, convert existing values."""
    # Map database enum values to user-friendly ranges
    enum_to_range = {
        "Under18": "Under 18",
        "Age18_24": "18-29",
        "Age25_34": "30-39",
        "Age35_44": "40-49",
        "Age45_54": "50-59",
        "Age55Plus": "60+",
    }

    # Add new string column temporarily
    op.add_column(
        "user_profile", sa.Column("age_group_new", sa.String(), nullable=True)
    )

    # Convert existing enum values to string ranges
    for enum_val, range_val in enum_to_range.items():
        op.execute(
            f"""
            UPDATE user_profile
            SET age_group_new = '{range_val}'
            WHERE age_group::text = '{enum_val}'
        """
        )

    # Drop the old enum column
    op.drop_column("user_profile", "age_group")

    # Rename the new column to the original name
    op.alter_column("user_profile", "age_group_new", new_column_name="age_group")

    # Make it NOT NULL
    op.alter_column("user_profile", "age_group", nullable=False)


def downgrade() -> None:
    """Downgrade schema: change age_group back to enum."""
    # Reverse mapping from ranges back to enum values
    range_to_enum = {
        "Under 18": "Under18",
        "18-29": "Age18_24",
        "30-39": "Age25_34",
        "40-49": "Age35_44",
        "50-59": "Age45_54",
        "60+": "Age55Plus",
    }

    # Add enum column back
    op.add_column(
        "user_profile",
        sa.Column(
            "age_group_enum",
            sa.Enum(
                "Under18",
                "Age18_24",
                "Age25_34",
                "Age35_44",
                "Age45_54",
                "Age55Plus",
                name="agegroup",
            ),
            nullable=True,
        ),
    )

    # Convert string ranges back to enum values
    for range_val, enum_val in range_to_enum.items():
        op.execute(
            f"""
            UPDATE user_profile
            SET age_group_enum = '{enum_val}'
            WHERE age_group = '{range_val}'
        """
        )

    # Drop the string column
    op.drop_column("user_profile", "age_group")

    # Rename enum column back
    op.alter_column("user_profile", "age_group_enum", new_column_name="age_group")

    # Make it NOT NULL
    op.alter_column("user_profile", "age_group", nullable=False)
