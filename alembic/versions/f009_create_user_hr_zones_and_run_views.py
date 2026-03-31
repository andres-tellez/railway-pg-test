"""create user_hr_zones table, v_run_metrics view, v_easy_runs view

Revision ID: f009
Revises: f008
Create Date: 2026-03-27

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f009"
down_revision: Union[str, None] = "f008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREATE_USER_HR_ZONES = """
CREATE TABLE IF NOT EXISTS user_hr_zones (
    user_id UUID PRIMARY KEY,
    z1_low  DOUBLE PRECISION,
    z1_high DOUBLE PRECISION,
    z2_low  DOUBLE PRECISION,
    z2_high DOUBLE PRECISION,
    z3_low  DOUBLE PRECISION,
    z3_high DOUBLE PRECISION,
    z4_low  DOUBLE PRECISION,
    z4_high DOUBLE PRECISION,
    z5_low  DOUBLE PRECISION,
    z5_high DOUBLE PRECISION,
    method  VARCHAR NOT NULL,
    hrmax_used     DOUBLE PRECISION,
    resting_hr_used DOUBLE PRECISION,
    computed_at TIMESTAMPTZ DEFAULT now()
)
"""

_CREATE_V_RUN_METRICS = """
CREATE OR REPLACE VIEW v_run_metrics AS
WITH split_half AS (
    SELECT
        s.activity_id,
        s.split,
        s.average_heartrate,
        s.conv_avg_speed,
        (COUNT(*) OVER (PARTITION BY s.activity_id))::int AS total_splits,
        ((COUNT(*) OVER (PARTITION BY s.activity_id)) / 2.0) AS half_point
    FROM splits s
    WHERE s.average_heartrate IS NOT NULL
)
SELECT
    a.activity_id,
    a.user_id,
    a.type            AS activity_type,
    a.name            AS activity_name,
    a.start_date,
    to_char(
        (a.start_date AT TIME ZONE 'UTC')
            AT TIME ZONE COALESCE(
                split_part(a.timezone, ') ', 2),
                'UTC'
            ),
        'YYYY-MM-DD'
    ) AS activity_date,
    a.moving_time     AS moving_time_seconds,
    a.average_heartrate AS avg_hr,
    a.max_heartrate   AS max_hr,
    a.conv_distance   AS distance_miles,
    a.conv_avg_speed  AS avg_pace,
    a.suffer_score,

    z.z2_low,
    z.z2_high,
    z.method          AS zone_method,

    sh.total_splits,

    -- EASY_PCT: splits at or below Z2 ceiling (for classifier)
    CASE WHEN z.z2_high IS NOT NULL AND sh.total_splits > 0 THEN
        COUNT(CASE WHEN sh.average_heartrate <= z.z2_high THEN 1 END)::float
        / sh.total_splits
    ELSE NULL END AS easy_pct,

    -- Z2_BAND_PCT: splits strictly within Z2 band (for KPI)
    CASE WHEN z.z2_low IS NOT NULL AND z.z2_high IS NOT NULL AND sh.total_splits > 0 THEN
        COUNT(CASE WHEN sh.average_heartrate BETWEEN z.z2_low AND z.z2_high THEN 1 END)::float
        / sh.total_splits
    ELSE NULL END AS z2_band_pct,

    -- EARLY / LATE HR (half-run split for drift)
    AVG(sh.average_heartrate) FILTER (WHERE sh.split <= sh.half_point) AS early_hr,
    AVG(sh.average_heartrate) FILTER (WHERE sh.split > sh.half_point)  AS late_hr,

    -- HR DRIFT %
    CASE
        WHEN AVG(sh.average_heartrate) FILTER (WHERE sh.split <= sh.half_point) > 0
         AND AVG(sh.average_heartrate) FILTER (WHERE sh.split > sh.half_point) IS NOT NULL
        THEN (
            (AVG(sh.average_heartrate) FILTER (WHERE sh.split > sh.half_point)
             - AVG(sh.average_heartrate) FILTER (WHERE sh.split <= sh.half_point))
            / NULLIF(AVG(sh.average_heartrate) FILTER (WHERE sh.split <= sh.half_point), 0)
            * 100.0
        )
        ELSE NULL
    END AS hr_drift_pct,

    -- PEAK SPLIT HR
    MAX(sh.average_heartrate) AS peak_split_hr,

    -- PACE (conv_avg_speed is min/mi — lower = faster)
    MIN(sh.conv_avg_speed)    AS fastest_split_pace,
    MAX(sh.conv_avg_speed)    AS slowest_split_pace,
    MAX(sh.conv_avg_speed) - MIN(sh.conv_avg_speed) AS pace_spread

FROM activities a
JOIN split_half sh ON a.activity_id = sh.activity_id
LEFT JOIN user_hr_zones z ON a.user_id = z.user_id
WHERE a.conv_distance > 0
GROUP BY
    a.activity_id, a.user_id, a.type, a.name, a.start_date,
    a.moving_time, a.average_heartrate, a.max_heartrate,
    a.conv_distance, a.conv_avg_speed, a.suffer_score,
    z.z2_low, z.z2_high, z.method,
    sh.total_splits
"""

_CREATE_V_EASY_RUNS = """
CREATE OR REPLACE VIEW v_easy_runs AS
SELECT *,
    (
        activity_type = 'Run'
        AND moving_time_seconds >= 1800  -- EASY_RUN_THRESHOLDS.MIN_DURATION_SECONDS
        AND easy_pct >= 0.70             -- EASY_RUN_THRESHOLDS.MIN_EASY_PCT
        AND z2_high IS NOT NULL
    ) AS is_easy_run
FROM v_run_metrics
"""


def upgrade() -> None:
    op.execute(_CREATE_USER_HR_ZONES)
    op.execute(_CREATE_V_RUN_METRICS)
    op.execute(_CREATE_V_EASY_RUNS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_easy_runs")
    op.execute("DROP VIEW IF EXISTS v_run_metrics")
    op.execute("DROP TABLE IF EXISTS user_hr_zones")
