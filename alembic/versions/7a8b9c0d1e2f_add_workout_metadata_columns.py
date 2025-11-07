"""add_workout_metadata_columns

Revision ID: 7a8b9c0d1e2f
Revises: cc57a44b0d46
Create Date: 2026-01-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7a8b9c0d1e2f"
down_revision: Union[str, None] = "cc57a44b0d46"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add workout metadata columns to plan_workouts table."""
    # Add new columns (all nullable for backward compatibility)
    op.add_column(
        "plan_workouts",
        sa.Column(
            "run_type_key",
            sa.Text(),
            nullable=True,
            comment="Canonical type: easy|steady|endurance|long",
        ),
    )
    op.add_column(
        "plan_workouts",
        sa.Column(
            "phase",
            sa.Text(),
            nullable=True,
            comment="Training phase: Base|Build|Peak|Taper",
        ),
    )
    op.add_column(
        "plan_workouts",
        sa.Column(
            "pace_ranges",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Pace ranges: {E:[sec,sec], S:[...], M:[...], T:[...]}",
        ),
    )
    op.add_column(
        "plan_workouts",
        sa.Column(
            "allow_quality",
            sa.Boolean(),
            nullable=True,
            comment="Whether quality elements allowed",
        ),
    )
    op.add_column(
        "plan_workouts",
        sa.Column(
            "cues",
            sa.Text(),
            nullable=True,
            comment="Athlete-facing workout cues/guidance",
        ),
    )
    op.add_column(
        "plan_workouts",
        sa.Column(
            "quality_insert",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Quality insert metadata: {type: 'marathon_finish'|'strides', miles: ...}",
        ),
    )

    # Add check constraint
    op.create_check_constraint(
        "chk_run_type_key",
        "plan_workouts",
        "run_type_key IN ('easy','steady','endurance','long')",
    )

    # Add index for plan_id, date lookups
    op.create_index(
        "idx_plan_workouts_plan_date",
        "plan_workouts",
        ["plan_id", "date"],
    )


def downgrade() -> None:
    """Remove workout metadata columns from plan_workouts table."""
    op.drop_index("idx_plan_workouts_plan_date", table_name="plan_workouts")
    op.drop_constraint("chk_run_type_key", "plan_workouts", type_="check")
    op.drop_column("plan_workouts", "quality_insert")
    op.drop_column("plan_workouts", "cues")
    op.drop_column("plan_workouts", "allow_quality")
    op.drop_column("plan_workouts", "pace_ranges")
    op.drop_column("plan_workouts", "phase")
    op.drop_column("plan_workouts", "run_type_key")
