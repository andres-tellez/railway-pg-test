"""create plan_workouts table

Revision ID: b48a3cb768f1
Revises: 6d996face68b
Create Date: 2025-09-13 17:19:11.495642

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b48a3cb768f1"
down_revision: Union[str, None] = "6d996face68b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create plan_workouts table."""
    op.create_table(
        "plan_workouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("workout_type", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("miles", sa.Float(), nullable=False),
        sa.Column("intensity", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("plan_id", "date", name="uq_plan_date"),
    )


def downgrade() -> None:
    """Downgrade schema: drop plan_workouts table."""
    op.drop_table("plan_workouts")
