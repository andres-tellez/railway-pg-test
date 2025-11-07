-- =====================================================
-- Longest Runs Materialized View
-- =====================================================
-- Pre-calculates longest run per week with all metadata
-- Follows same optimization pattern as mv_athlete_metrics
-- =====================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_longest_runs AS
WITH weekly_longest AS (
    SELECT
        athlete_id,
        DATE_TRUNC('week', start_date) AS week_start,
        MAX(distance) AS max_distance
    FROM activities
    WHERE type = 'Run'
      AND distance > 0
      AND start_date >= CURRENT_DATE - INTERVAL '20 weeks'
    GROUP BY athlete_id, DATE_TRUNC('week', start_date)
),
run_details AS (
    SELECT
        a.athlete_id,
        DATE_TRUNC('week', a.start_date) AS week_start,
        a.activity_id,
        a.name,
        a.start_date,
        a.distance / 1609.34 AS distance_miles,
        a.moving_time,
        a.average_speed,
        a.hr_zone_1,
        a.hr_zone_2,
        a.hr_zone_3,
        a.hr_zone_4,
        a.hr_zone_5,
        wl.max_distance / 1609.34 AS week_max_distance
    FROM activities a
    INNER JOIN weekly_longest wl
        ON a.athlete_id = wl.athlete_id
        AND DATE_TRUNC('week', a.start_date) = wl.week_start
        AND a.distance = wl.max_distance
    WHERE a.type = 'Run'
      AND a.distance > 0
      AND a.start_date >= CURRENT_DATE - INTERVAL '20 weeks'
),
all_time_max AS (
    SELECT
        athlete_id,
        MAX(distance) / 1609.34 AS all_time_max_distance
    FROM activities
    WHERE type = 'Run'
      AND distance > 0
      AND start_date >= CURRENT_DATE - INTERVAL '52 weeks'  -- Look back 1 year for PR detection
    GROUP BY athlete_id
),
week_comparisons AS (
    SELECT
        rd.athlete_id,
        rd.week_start,
        rd.activity_id,
        rd.name,
        rd.start_date,
        rd.distance_miles,
        rd.moving_time,
        rd.average_speed,
        rd.hr_zone_1,
        rd.hr_zone_2,
        rd.hr_zone_3,
        rd.hr_zone_4,
        rd.hr_zone_5,
        rd.week_max_distance,
        atm.all_time_max_distance,
        LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) AS prev_week_distance,
        -- Pre-calculate is_personal_record (within 1 year window)
        CASE
            WHEN rd.week_max_distance >= atm.all_time_max_distance THEN true
            ELSE false
        END AS is_personal_record,
        -- Pre-calculate is_significant_drop (smart taper detection)
        -- RED flag if: (1) >20% drop AND previous week also dropped >10%, OR (2) single week >30% drop
        CASE
            WHEN LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) IS NOT NULL
                 AND rd.week_max_distance >= 1.0  -- Only flag if run is at least 1 mile
                 AND (
                     -- Pattern 1: Two consecutive drops (20% + 10%)
                     (rd.week_max_distance < (LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) * 0.8)
                      AND LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start)
                          < (LAG(rd.week_max_distance, 2) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) * 0.9))
                     -- Pattern 2: Single dramatic drop (>30%)
                     OR rd.week_max_distance < (LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) * 0.7)
                 )
            THEN true
            ELSE false
        END AS is_significant_drop,
        -- Pre-calculate trend
        CASE
            WHEN LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) IS NULL THEN 'stable'
            WHEN rd.week_max_distance > (LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) * 1.05) THEN 'improving'
            WHEN rd.week_max_distance < (LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) * 0.95) THEN 'declining'
            ELSE 'stable'
        END AS trend,
        -- Pre-calculate change percentage
        CASE
            WHEN LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start) IS NOT NULL
            THEN ((rd.week_max_distance - LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start))
                  / LAG(rd.week_max_distance) OVER (PARTITION BY rd.athlete_id ORDER BY rd.week_start)) * 100
            ELSE 0
        END AS change_pct
    FROM run_details rd
    LEFT JOIN all_time_max atm ON rd.athlete_id = atm.athlete_id
),
aggregated_data AS (
    SELECT
        athlete_id,
        JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'week_start', week_start,
                'activity_id', activity_id,
                'name', name,
                'date', start_date,
                'distance', ROUND(distance_miles::numeric, 2),
                'moving_time', moving_time,
                'average_speed', average_speed,
                'heart_rate_zones', JSONB_BUILD_OBJECT(
                    'zone_1', hr_zone_1,
                    'zone_2', hr_zone_2,
                    'zone_3', hr_zone_3,
                    'zone_4', hr_zone_4,
                    'zone_5', hr_zone_5
                ),
                'is_personal_record', is_personal_record,
                'is_significant_drop', is_significant_drop,
                'trend', trend,
                'change_pct', ROUND(change_pct::numeric, 1),
                'prev_week_distance', ROUND(prev_week_distance::numeric, 2)
            ) ORDER BY week_start DESC
        ) AS weekly_runs
    FROM week_comparisons
    GROUP BY athlete_id
),
summary_stats AS (
    SELECT
        wc.athlete_id,
        COUNT(*) AS total_weeks,
        COUNT(*) FILTER (WHERE wc.is_personal_record = true) AS pr_count,
        COUNT(*) FILTER (WHERE wc.is_significant_drop = true) AS drop_count,
        COUNT(*) FILTER (WHERE wc.trend = 'improving') AS improving_weeks
    FROM week_comparisons wc
    GROUP BY wc.athlete_id
)
SELECT
    ad.athlete_id,
    ad.weekly_runs,
    ss.total_weeks,
    ss.pr_count,
    ss.drop_count,
    ss.improving_weeks
FROM aggregated_data ad
INNER JOIN summary_stats ss ON ad.athlete_id = ss.athlete_id;

-- Create indexes for fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_longest_runs_athlete
    ON mv_longest_runs(athlete_id);

-- Refresh the view (will be done automatically via cron or on-demand)
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_longest_runs;
