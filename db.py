import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from typing import Dict, Optional, List

# Only load .env when running locally
if os.getenv("FLASK_ENV") == "development":
    load_dotenv()

def get_conn():
    """
    Establish a connection to Postgres via the single DATABASE_URL env var.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")
    conn = psycopg2.connect(db_url, sslmode="require")
    with conn.cursor() as cur:
        cur.execute("SET search_path TO public;")
    return conn

def save_token_pg(athlete_id: int, access_token: str, refresh_token: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tokens (athlete_id, access_token, refresh_token)
                VALUES (%s, %s, %s)
                ON CONFLICT (athlete_id)
                DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    updated_at = CURRENT_TIMESTAMP;
            """, (athlete_id, access_token, refresh_token))

def get_tokens_pg(athlete_id: int) -> Optional[Dict[str, str]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT access_token, refresh_token
                FROM tokens
                WHERE athlete_id = %s;
            """, (athlete_id,))
            return cur.fetchone()

def save_activity_pg(activity: Dict) -> None:
    try:
        activity_id     = activity["id"]
        athlete_id      = activity["athlete"]["id"]
        name            = activity["name"]
        start_date      = activity.get("start_date_local") or activity.get("start_date")
        distance_m      = activity.get("distance", 0)
        moving_s        = activity.get("moving_time", 0)

        distance_mi     = round(distance_m / 1609.34, 2) if distance_m else 0
        moving_time_min = round(moving_s   / 60,     2) if moving_s   else 0
        pace            = round(moving_time_min / distance_mi, 2) if distance_mi and moving_time_min else None
        full_json       = json.dumps(activity)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO activities (
                        activity_id, athlete_id, name, start_date,
                        distance_mi, moving_time_min, average_speed_min_per_mile, data
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING;
                """, (
                    activity_id,
                    athlete_id,
                    name,
                    start_date,
                    distance_mi,
                    moving_time_min,
                    pace,
                    full_json
                ))
    except Exception as e:
        print(f"❌ Failed to save activity {activity.get('id', '?')}: {e}")

def save_run_splits(activity_id: int, splits: List[Dict]) -> None:
    """
    Insert or update per-mile splits for an activity.
    """
    conn = get_conn()
    with conn.cursor() as cur:
        for s in splits:
            cur.execute("""
                INSERT INTO run_splits (
                    activity_id, segment_index,
                    distance_m, elapsed_time, pace, average_heartrate
                ) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (activity_id, segment_index)
                DO UPDATE SET
                    elapsed_time = EXCLUDED.elapsed_time,
                    pace = EXCLUDED.pace,
                    average_heartrate = EXCLUDED.average_heartrate;
            """, (
                activity_id,
                s["segment_index"],
                s["distance"],
                s["elapsed_time"],
                s["pace"],
                s.get("average_heartrate")
            ))
    conn.commit()
    conn.close()
