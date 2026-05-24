"""Backfill plan_workouts.pace_ranges to zone-native keys and drop legacy E/S/T/M.

Revision ID: f020
Revises: f019
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f020"
down_revision: Union[str, None] = "f019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Copy legacy letter keys into z2/z3/z4/m when canonical keys are missing,
    then remove E/S/T/M keys from the JSON object.
    """
    op.execute(
        """
        UPDATE plan_workouts
        SET pace_ranges = (
            CASE
                WHEN pace_ranges IS NULL THEN NULL
                ELSE
                    pace_ranges
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'z2') AND (pace_ranges ? 'E')
                            THEN jsonb_build_object('z2', pace_ranges->'E')
                            ELSE '{}'::jsonb
                        END
                    )
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'z3') AND (pace_ranges ? 'S')
                            THEN jsonb_build_object('z3', pace_ranges->'S')
                            ELSE '{}'::jsonb
                        END
                    )
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'z4') AND (pace_ranges ? 'T')
                            THEN jsonb_build_object('z4', pace_ranges->'T')
                            ELSE '{}'::jsonb
                        END
                    )
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'm') AND (pace_ranges ? 'M')
                            THEN jsonb_build_object('m', pace_ranges->'M')
                            ELSE '{}'::jsonb
                        END
                    )
                    - 'E' - 'S' - 'T' - 'M'
            END
        )
        WHERE pace_ranges IS NOT NULL
          AND jsonb_typeof(pace_ranges) = 'object'
        """
    )


def downgrade() -> None:
    """
    Best-effort: add legacy letter keys alongside zone-native payloads for rollback.

    Canonical z2/z3/z4/m keys are retained.
    """
    op.execute(
        """
        UPDATE plan_workouts
        SET pace_ranges = (
            CASE
                WHEN pace_ranges IS NULL THEN NULL
                ELSE
                    pace_ranges
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'E') AND (pace_ranges ? 'z2')
                            THEN jsonb_build_object('E', pace_ranges->'z2')
                            ELSE '{}'::jsonb
                        END
                    )
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'S') AND (pace_ranges ? 'z3')
                            THEN jsonb_build_object('S', pace_ranges->'z3')
                            ELSE '{}'::jsonb
                        END
                    )
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'T') AND (pace_ranges ? 'z4')
                            THEN jsonb_build_object('T', pace_ranges->'z4')
                            ELSE '{}'::jsonb
                        END
                    )
                    || (
                        CASE
                            WHEN NOT (pace_ranges ? 'M') AND (pace_ranges ? 'm')
                            THEN jsonb_build_object('M', pace_ranges->'m')
                            ELSE '{}'::jsonb
                        END
                    )
            END
        )
        WHERE pace_ranges IS NOT NULL
          AND jsonb_typeof(pace_ranges) = 'object'
        """
    )
