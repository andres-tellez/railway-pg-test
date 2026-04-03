#!/usr/bin/env python3
"""
Backfill user_hr_zones for all existing users who have max_hr in their profile.

Creates the user_hr_zones table and SQL views if they don't already exist,
then populates zones for every user with max_hr set.

Usage:
    python scripts/backfill_user_hr_zones.py
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env.local")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.services.heart_rate.zone_population_service import refresh_user_zones

_CREATE_TABLE = """
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


def main():
    env_key = "PROD_DATABASE_URL" if "--prod" in sys.argv else "DATABASE_URL"
    db_url = os.environ.get(env_key)
    if not db_url:
        print(f"ERROR: {env_key} not set")
        sys.exit(1)
    print(f"Using {env_key} -> {db_url.split('@')[1].split('/')[0]}")

    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # --- Step 1: Create table + views ---
        print("Creating user_hr_zones table (if not exists)...")
        session.execute(text(_CREATE_TABLE))
        session.commit()
        print("  Done.")

        print("Creating activity_local_date function...")
        session.execute(text(_CREATE_ACTIVITY_LOCAL_DATE_FN))
        session.commit()
        print("  Done.")

        print("Creating v_run_metrics view...")
        session.execute(text(_CREATE_V_RUN_METRICS))
        session.commit()
        print("  Done.")

        print("Creating v_easy_runs view...")
        session.execute(text(_CREATE_V_EASY_RUNS))
        session.commit()
        print("  Done.")

        # --- Step 2: Backfill zones for all users with max_hr ---
        rows = session.execute(
            text("SELECT user_id FROM user_profile WHERE max_hr IS NOT NULL")
        ).fetchall()

        print(f"\nFound {len(rows)} user(s) with max_hr set")

        success = 0
        skipped = 0
        errors = 0

        for (user_id,) in rows:
            try:
                result = refresh_user_zones(session, str(user_id))
                if result:
                    print(
                        f"  OK {user_id}: {result['method']} "
                        f"z2={result['z2_low']:.1f}-{result['z2_high']:.1f}"
                    )
                    success += 1
                else:
                    print(f"  -- {user_id}: skipped (insufficient data)")
                    skipped += 1
            except Exception as e:
                print(f"  FAIL {user_id}: {e}")
                session.rollback()
                errors += 1

        # --- Step 3: Validate ---
        print(f"\nBackfill: {success} populated, {skipped} skipped, {errors} errors")

        count = session.execute(text("SELECT COUNT(*) FROM user_hr_zones")).scalar()
        print(f"user_hr_zones rows: {count}")

        easy = session.execute(
            text("SELECT COUNT(*) FROM v_easy_runs WHERE is_easy_run = TRUE")
        ).scalar()
        print(f"Easy runs found: {easy}")

        if easy > 0:
            sample = session.execute(
                text(
                    """
                    SELECT activity_date, activity_name, distance_miles,
                           ROUND(easy_pct::numeric, 2) AS easy_pct,
                           ROUND(z2_band_pct::numeric, 2) AS z2_band_pct,
                           ROUND(hr_drift_pct::numeric, 2) AS hr_drift_pct,
                           is_easy_run
                    FROM v_easy_runs
                    WHERE is_easy_run = TRUE
                    ORDER BY activity_date DESC
                    LIMIT 10
                """
                )
            ).fetchall()
            print("\nSample easy runs:")
            for r in sample:
                print(
                    f"  {r[0]}  {r[1]:<30}  {r[2]:>5.1f}mi  "
                    f"easy={r[3]}  z2band={r[4]}  drift={r[5]}%"
                )

    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
