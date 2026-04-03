"""add activity_local_date function and align run views

Revision ID: f010
Revises: f009
Create Date: 2026-04-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f010"
down_revision: Union[str, None] = "f009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREATE_ACTIVITY_LOCAL_DATE_FN = """
CREATE OR REPLACE FUNCTION activity_local_date(
    p_start_date TIMESTAMPTZ,
    p_timezone TEXT
) RETURNS DATE
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT
    CASE
        WHEN p_timezone IS NOT NULL AND p_timezone LIKE '%America/%' THEN
            DATE((p_start_date AT TIME ZONE 'UTC') AT TIME ZONE
                SUBSTRING(p_timezone FROM POSITION(') ' IN p_timezone) + 2))
        WHEN p_timezone IS NOT NULL THEN
            DATE((p_start_date AT TIME ZONE 'UTC') AT TIME ZONE
                COALESCE(
                    NULLIF(SUBSTRING(p_timezone FROM POSITION(') ' IN p_timezone) + 2), ''),
                    'UTC'
                ))
        ELSE
            DATE(p_start_date)
    END
$$
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
    to_char(activity_local_date(a.start_date, a.timezone), 'YYYY-MM-DD') AS activity_date,
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

    CASE WHEN z.z2_high IS NOT NULL AND sh.total_splits > 0 THEN
        COUNT(CASE WHEN sh.average_heartrate <= z.z2_high THEN 1 END)::float
        / sh.total_splits
    ELSE NULL END AS easy_pct,

    CASE WHEN z.z2_low IS NOT NULL AND z.z2_high IS NOT NULL AND sh.total_splits > 0 THEN
        COUNT(CASE WHEN sh.average_heartrate BETWEEN z.z2_low AND z.z2_high THEN 1 END)::float
        / sh.total_splits
    ELSE NULL END AS z2_band_pct,

    AVG(sh.average_heartrate) FILTER (WHERE sh.split <= sh.half_point) AS early_hr,
    AVG(sh.average_heartrate) FILTER (WHERE sh.split > sh.half_point)  AS late_hr,

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

    MAX(sh.average_heartrate) AS peak_split_hr,

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

_CREATE_V_RUN_METRICS_LEGACY = """
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

    CASE WHEN z.z2_high IS NOT NULL AND sh.total_splits > 0 THEN
        COUNT(CASE WHEN sh.average_heartrate <= z.z2_high THEN 1 END)::float
        / sh.total_splits
    ELSE NULL END AS easy_pct,

    CASE WHEN z.z2_low IS NOT NULL AND z.z2_high IS NOT NULL AND sh.total_splits > 0 THEN
        COUNT(CASE WHEN sh.average_heartrate BETWEEN z.z2_low AND z.z2_high THEN 1 END)::float
        / sh.total_splits
    ELSE NULL END AS z2_band_pct,

    AVG(sh.average_heartrate) FILTER (WHERE sh.split <= sh.half_point) AS early_hr,
    AVG(sh.average_heartrate) FILTER (WHERE sh.split > sh.half_point)  AS late_hr,

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

    MAX(sh.average_heartrate) AS peak_split_hr,

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


def upgrade() -> None:
    op.execute(_CREATE_ACTIVITY_LOCAL_DATE_FN)
    op.execute(_CREATE_V_RUN_METRICS)


def downgrade() -> None:
    op.execute(_CREATE_V_RUN_METRICS_LEGACY)
    op.execute("DROP FUNCTION IF EXISTS activity_local_date(TIMESTAMPTZ, TEXT)")
