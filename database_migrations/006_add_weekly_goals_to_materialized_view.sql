-- Add weekly goals to materialized view with correct date calculation
-- This fixes the 2026 vs 2025 timezone issue using 16 weeks of history

-- First, drop the existing materialized view
DROP MATERIALIZED VIEW IF EXISTS mv_athlete_metrics;

-- Recreate with weekly goals included and correct timezone handling
CREATE MATERIALIZED VIEW mv_athlete_metrics AS
WITH weekly_data AS (
    SELECT
        athlete_id,
        DATE_TRUNC('week', start_date) AS week_start,
        SUM(distance) / 1609.34 AS distance_miles,
        COUNT(*) AS run_count,
        AVG(distance / NULLIF(moving_time, 0)) AS avg_speed_mps,
        SUM(hr_zone_1) AS hr_zone_1,
        SUM(hr_zone_2) AS hr_zone_2,
        SUM(hr_zone_3) AS hr_zone_3,
        SUM(hr_zone_4) AS hr_zone_4,
        SUM(hr_zone_5) AS hr_zone_5,
        SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
            COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) AS total_hr_time,
        -- VO2 Max estimation from run_score
        MAX(run_score) AS best_run_score,
        CASE
            WHEN MAX(run_score) IS NOT NULL
            THEN ROUND((MAX(run_score) / 100.0) + 30, 1)
            ELSE NULL
        END AS vo2_estimate
    FROM activities
    WHERE type = 'Run'
      AND distance > 0
      AND start_date >= CURRENT_DATE - INTERVAL '20 weeks'
    GROUP BY athlete_id, DATE_TRUNC('week', start_date)
),
-- Add weekly goals calculation from active training plans
-- Only show 16 weeks of history including current week (no future weeks)
weekly_goals AS (
    SELECT
        ua.athlete_id,
        DATE_TRUNC('week', pw.date::timestamp) AS week_start,
        SUM(pw.miles) AS goal_miles
    FROM user_athletes ua
    JOIN plans p ON p.user_id = ua.user_id AND p.is_active = true
    JOIN plan_workouts pw ON pw.plan_id = p.id
    WHERE pw.date >= CURRENT_DATE - INTERVAL '16 weeks'  -- 16 weeks of history
      AND pw.date <= CURRENT_DATE  -- Up to current date only
    GROUP BY ua.athlete_id, DATE_TRUNC('week', pw.date::timestamp)
),
current_week AS (
    SELECT
        athlete_id,
        SUM(distance_miles) AS current_distance,
        SUM(run_count) AS current_runs,
        AVG(avg_speed_mps) AS current_avg_speed
    FROM weekly_data
    WHERE week_start = DATE_TRUNC('week', CURRENT_DATE)
    GROUP BY athlete_id
),
previous_week AS (
    SELECT
        athlete_id,
        SUM(distance_miles) AS previous_distance,
        SUM(run_count) AS previous_runs,
        AVG(avg_speed_mps) AS previous_avg_speed
    FROM weekly_data
    WHERE week_start = DATE_TRUNC('week', CURRENT_DATE - INTERVAL '1 week')
    GROUP BY athlete_id
),
hr_zones_30d AS (
    SELECT
        athlete_id,
        SUM(hr_zone_1) AS zone_1_time,
        SUM(hr_zone_2) AS zone_2_time,
        SUM(hr_zone_3) AS zone_3_time,
        SUM(hr_zone_4) AS zone_4_time,
        SUM(hr_zone_5) AS zone_5_time,
        SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
            COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) AS total_hr_time,
        -- Pre-calculate percentages
        CASE
            WHEN SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
                     COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) > 0
            THEN (SUM(hr_zone_1)::FLOAT / SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) +
                  COALESCE(hr_zone_3, 0) + COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0))::FLOAT) * 100
            ELSE 0
        END AS zone_1_pct,
        CASE
            WHEN SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
                     COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) > 0
            THEN (SUM(hr_zone_2)::FLOAT / SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) +
                  COALESCE(hr_zone_3, 0) + COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0))::FLOAT) * 100
            ELSE 0
        END AS zone_2_pct,
        CASE
            WHEN SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
                     COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) > 0
            THEN (SUM(hr_zone_3)::FLOAT / SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) +
                  COALESCE(hr_zone_3, 0) + COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0))::FLOAT) * 100
            ELSE 0
        END AS zone_3_pct,
        CASE
            WHEN SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
                     COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) > 0
            THEN (SUM(hr_zone_4)::FLOAT / SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) +
                  COALESCE(hr_zone_3, 0) + COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0))::FLOAT) * 100
            ELSE 0
        END AS zone_4_pct,
        CASE
            WHEN SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) + COALESCE(hr_zone_3, 0) +
                     COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0)) > 0
            THEN (SUM(hr_zone_5)::FLOAT / SUM(COALESCE(hr_zone_1, 0) + COALESCE(hr_zone_2, 0) +
                  COALESCE(hr_zone_3, 0) + COALESCE(hr_zone_4, 0) + COALESCE(hr_zone_5, 0))::FLOAT) * 100
            ELSE 0
        END AS zone_5_pct
    FROM activities
    WHERE type = 'Run'
      AND distance > 0
      AND start_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY athlete_id
)
SELECT
    COALESCE(cw.athlete_id, pw.athlete_id, hz.athlete_id) AS athlete_id,
    COALESCE(cw.current_distance, 0) AS current_distance,
    COALESCE(pw.previous_distance, 0) AS previous_distance,
    COALESCE(cw.current_runs, 0) AS current_runs,
    COALESCE(pw.previous_runs, 0) AS previous_runs,
    cw.current_avg_speed,
    pw.previous_avg_speed,
    -- Pre-calculate percentage changes
    CASE
        WHEN pw.previous_distance > 0
        THEN ((cw.current_distance - pw.previous_distance) / pw.previous_distance) * 100
        ELSE 0
    END AS distance_change_pct,
    CASE
        WHEN pw.previous_runs > 0
        THEN ((cw.current_runs::FLOAT - pw.previous_runs::FLOAT) / pw.previous_runs::FLOAT) * 100
        ELSE 0
    END AS runs_change_pct,
    hz.zone_1_pct,
    hz.zone_2_pct,
    hz.zone_3_pct,
    hz.zone_4_pct,
    hz.zone_5_pct,
    -- Include weekly data for trends (including VO2 estimates)
    (SELECT json_agg(
        json_build_object(
            'week', week_start,
            'distance', ROUND(distance_miles::NUMERIC, 1),
            'runs', run_count,
            'avg_speed_mps', avg_speed_mps,
            'hr_zone_1', hr_zone_1,
            'hr_zone_2', hr_zone_2,
            'hr_zone_3', hr_zone_3,
            'hr_zone_4', hr_zone_4,
            'hr_zone_5', hr_zone_5,
            'total_hr_time', total_hr_time,
            'best_run_score', best_run_score,
            'vo2_estimate', vo2_estimate
        ) ORDER BY week_start DESC
    ) FROM weekly_data wd WHERE wd.athlete_id = COALESCE(cw.athlete_id, pw.athlete_id, hz.athlete_id)) AS weekly_data,
    -- Include weekly goals with correct date calculation
    (SELECT json_agg(
        json_build_object(
            'week', week_start,
            'goal_miles', ROUND(goal_miles::NUMERIC, 1)
        ) ORDER BY week_start DESC
    ) FROM weekly_goals wg WHERE wg.athlete_id = COALESCE(cw.athlete_id, pw.athlete_id, hz.athlete_id)) AS weekly_goals
FROM current_week cw
FULL OUTER JOIN previous_week pw ON cw.athlete_id = pw.athlete_id
FULL OUTER JOIN hr_zones_30d hz ON COALESCE(cw.athlete_id, pw.athlete_id) = hz.athlete_id;

-- Recreate the index
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_athlete_metrics_athlete_id ON mv_athlete_metrics(athlete_id);

-- Refresh the materialized view
REFRESH MATERIALIZED VIEW mv_athlete_metrics;
