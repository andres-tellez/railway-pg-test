"""Add activity execution scoring and plan-match fields.

Revision ID: f014
Revises: f013
Create Date: 2026-04-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f014"
down_revision: Union[str, None] = "f013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("matched_plan_workout_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "activities", sa.Column("planned_type", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "activities", sa.Column("executed_type", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "activities", sa.Column("zone_compliance_pct", sa.Float(), nullable=True)
    )
    op.add_column("activities", sa.Column("pct_above_zone", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("pct_below_zone", sa.Float(), nullable=True))
    op.add_column(
        "activities", sa.Column("run_score", sa.String(length=16), nullable=True)
    )
    op.add_column("activities", sa.Column("scoring_detail", sa.JSON(), nullable=True))
    op.add_column("activities", sa.Column("planned_miles", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("actual_miles", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("completion_pct", sa.Float(), nullable=True))

    op.create_index(
        "ix_activities_matched_plan_workout_id",
        "activities",
        ["matched_plan_workout_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_activities_matched_plan_workout_id",
        source_table="activities",
        referent_table="plan_workouts",
        local_cols=["matched_plan_workout_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_activities_matched_plan_workout_id", "activities", type_="foreignkey"
    )
    op.drop_index(
        "ix_activities_matched_plan_workout_id",
        table_name="activities",
    )
    op.drop_column("activities", "completion_pct")
    op.drop_column("activities", "actual_miles")
    op.drop_column("activities", "planned_miles")
    op.drop_column("activities", "scoring_detail")
    op.drop_column("activities", "run_score")
    op.drop_column("activities", "pct_below_zone")
    op.drop_column("activities", "pct_above_zone")
    op.drop_column("activities", "zone_compliance_pct")
    op.drop_column("activities", "executed_type")
    op.drop_column("activities", "planned_type")
    op.drop_column("activities", "matched_plan_workout_id")
