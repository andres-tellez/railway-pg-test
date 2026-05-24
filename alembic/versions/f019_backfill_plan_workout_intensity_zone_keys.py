"""Backfill plan_workouts.intensity to canonical pace-band keys

Revision ID: f019
Revises: f018
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f019"
down_revision: Union[str, None] = "f018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Normalize plan_workouts.intensity values to canonical pace-band keys.

    Canonical values: z2, z3, z4, m.
    """
    op.execute(
        """
        UPDATE plan_workouts
        SET intensity = CASE
            WHEN lower(coalesce(intensity, '')) IN ('z2', 'z3', 'z4', 'm')
                THEN lower(intensity)
            WHEN lower(coalesce(intensity, '')) IN ('e', 'easy', 'recovery')
                THEN 'z2'
            WHEN lower(coalesce(intensity, '')) IN ('s', 'steady', 'endurance')
                THEN 'z3'
            WHEN lower(coalesce(intensity, '')) IN ('t', 'threshold', 'tempo', 'vo2', 'intervals', 'repetitions', 'race')
                THEN 'z4'
            WHEN lower(coalesce(intensity, '')) IN ('m', 'marathon')
                THEN 'm'
            WHEN lower(coalesce(run_type_key, '')) IN ('steady', 'endurance', 'threshold', 'tempo')
                THEN 'z3'
            WHEN lower(coalesce(run_type_key, '')) IN ('vo2', 'intervals', 'repetitions', 'race')
                THEN 'z4'
            ELSE 'z2'
        END
        """
    )


def downgrade() -> None:
    """
    Restore legacy letter codes for intensity.
    """
    op.execute(
        """
        UPDATE plan_workouts
        SET intensity = CASE
            WHEN lower(coalesce(intensity, '')) = 'z2' THEN 'E'
            WHEN lower(coalesce(intensity, '')) = 'z3' THEN 'S'
            WHEN lower(coalesce(intensity, '')) = 'z4' THEN 'T'
            WHEN lower(coalesce(intensity, '')) = 'm' THEN 'M'
            ELSE 'E'
        END
        """
    )
