"""
Database utility module for Smart Marathon Coach (railway-pg-test).

Handles:
- Connecting to PostgreSQL via Railway DATABASE_URL
- Saving and retrieving Strava OAuth tokens
- Inserting and enriching Strava activity data in the 'activities' table
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    """
    Establish a connection to the Postgres instance using
    the single DATABASE_URL env var (private VPC), SSL enforced.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")
    conn = psycopg2.connect(db_url, sslmode="require")
    # ensure we’re on the public schema
    with conn.cursor() as cur:
        cur.execute("SET search_path TO public;")
    return conn

def save_token_pg(athlete_id, access_token, refresh_token):
    """
    Insert or update a Strava OAuth token for the given athlete.
    """
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

def get_token_pg(athlete_id):
    """
    Retrieve just the access_token for an athlete, or None if not found.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT access_token FROM tokens WHERE athlete_id = %s;", (athlete_id,))
            result = cur.fetchone()
            return result["access_token"] if result else None

def get_tokens_pg(athlete_id):
    """
    Retrieve both access_token and refresh_token for an athlete, or None.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT access_token, refresh_token
                FROM tokens
                WHERE athlete_id = %s;
            """, (athlete_id,))
            return cur.fetchone()

def save_activity_pg(activity):
    """
    Insert a new activity record into the 'activities' table.
    If it already exists, does nothing.
    """
    try:
        activity_id     = activity["id"]
        athlete_id      = activity["athlete"]["id"]
        name            = activity["name"]
        start_date      = activity["start_date_local"]
        distance_mi     = round(activity["distance"] / 1609.34, 2)
        moving_time_min = round(activity["moving_time"] / 60, 2)
        pace            = round(moving_time_min / distance_mi, 2)
        full_json       = json.dumps(activity)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO activities (
                        activity_id,
                        athlete_id,
                        name,
                        start_date,
                        distance_mi,
                        moving_time_min,
                        pace_min_per_mile,
                        data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (activity_id) DO NOTHING;
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

def enrich_activity_pg(activity_id, detailed_data):
    """
    Update the JSON data payload for an existing activity.
    """
    try:
        full_json = json.dumps(detailed_data)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE activities
                    SET data = %s
                    WHERE activity_id = %s;
                """, (full_json, activity_id))
    except Exception as e:
        print(f"❌ Failed to enrich activity {activity_id}: {e}")
