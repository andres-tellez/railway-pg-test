"""Migrate plan_workouts.run_type_key from placement roles to taxonomy keys.

Revision ID: f021
Revises: f020
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f021"
down_revision: Union[str, None] = "f020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plan_workouts
        SET run_type_key = 'easy'
        WHERE run_type_key = 'steady'
        """
    )
    op.execute(
        """
        UPDATE plan_workouts
        SET run_type_key = 'long_run'
        WHERE run_type_key = 'long'
        """
    )
    op.execute(
        """
        UPDATE plan_workouts
        SET run_type_key = CASE
            WHEN workout_type ILIKE '%race%' THEN 'race'
            WHEN workout_type ILIKE '%threshold%' THEN 'threshold'
            WHEN workout_type ILIKE '%tempo%' THEN 'tempo'
            WHEN workout_type ILIKE '%interval%' THEN 'intervals'
            WHEN workout_type ILIKE '%hill%' THEN 'hills'
            WHEN workout_type ILIKE '%long%' THEN 'long_run'
            ELSE 'easy'
        END
        WHERE run_type_key = 'endurance'
        """
    )
    op.execute(
        """
        ALTER TABLE plan_workouts
        DROP CONSTRAINT IF EXISTS chk_run_type_key
        """
    )
    op.execute(
        """
        ALTER TABLE plan_workouts
        ADD CONSTRAINT chk_run_type_key
        CHECK (
            run_type_key IS NULL
            OR run_type_key IN (
                'easy', 'tempo', 'threshold', 'long_run', 'intervals', 'hills', 'race'
            )
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE plan_workouts
        DROP CONSTRAINT IF EXISTS chk_run_type_key
        """
    )
    op.execute(
        """
        UPDATE plan_workouts
        SET run_type_key = CASE
            WHEN run_type_key IN ('tempo', 'threshold', 'intervals', 'hills') THEN 'endurance'
            WHEN run_type_key = 'long_run' THEN 'long'
            WHEN run_type_key = 'race' THEN 'endurance'
            ELSE run_type_key
        END
        WHERE run_type_key IS NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE plan_workouts
        ADD CONSTRAINT chk_run_type_key
        CHECK (
            run_type_key IS NULL
            OR run_type_key IN ('easy', 'steady', 'endurance', 'long')
        )
        """
    )
