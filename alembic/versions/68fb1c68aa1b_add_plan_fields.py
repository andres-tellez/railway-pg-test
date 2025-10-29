"""add_plan_fields

Revision ID: 68fb1c68aa1b
Revises: a1f25d836b46
Create Date: 2025-10-27 16:11:29.515730

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "68fb1c68aa1b"
down_revision: Union[str, None] = "a1f25d836b46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add plan-specific fields to plans table."""
    # Add columns for plan creation form fields
    op.add_column("plans", sa.Column("primary_goal", sa.String(50), nullable=True))
    op.add_column(
        "plans", sa.Column("marathon_experience", sa.String(50), nullable=True)
    )
    op.add_column("plans", sa.Column("target_time", sa.String(20), nullable=True))
    # Store training days specific to this plan (can differ from user profile)
    op.add_column(
        "plans", sa.Column("training_days", sa.ARRAY(sa.String()), nullable=True)
    )


def downgrade() -> None:
    """Remove plan-specific fields from plans table."""
    op.drop_column("plans", "training_days")
    op.drop_column("plans", "target_time")
    op.drop_column("plans", "marathon_experience")
    op.drop_column("plans", "primary_goal")
