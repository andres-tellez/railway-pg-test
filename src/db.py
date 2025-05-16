"""
Module: src/db.py
Database connection and token access helpers for Smart Marathon Coach.

Provides:
- `get_conn()`: Acquire a DB connection (SQLite or Postgres) based on environment.
- `get_tokens_pg()`: Fetch stored tokens for an athlete.
- `save_tokens_pg()`: Store or update tokens in the DB.
"""

import os
import sqlite3
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor


def get_conn(retries=5, delay=3):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")

    if db_url.startswith("sqlite"):
        # SQLite
        path = db_url.rsplit("///", 1)[-1]
        print(f"🔍 Connecting to SQLite at {path}", flush=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        print("✅ SQLite connection established", flush=True)
        return conn

    # Postgres
    parsed = urlparse(db_url)
    ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1") else "require"
    print(
        f"🔍 Connecting to Postgres at {parsed.hostname}:{parsed.port} with sslmode={ssl_mode}",
        flush=True,
    )
    conn = psycopg2.connect(dsn=db_url, sslmode=ssl_mode, connect_timeout=5)
    print("✅ Postgres connection established", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO public;")
    return conn


def get_tokens_pg(athlete_id: int):
    """
    Retrieve stored access and refresh tokens for an athlete.
    Returns a dict or None.
    """
    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute(
                "SELECT access_token, refresh_token FROM tokens WHERE athlete_id = ?",
                (athlete_id,),
            )
            row = cur.fetchone()
            return {"access_token": row[0], "refresh_token": row[1]} if row else None

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT access_token, refresh_token FROM tokens WHERE athlete_id = %s",
                (athlete_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def save_tokens_pg(athlete_id: int, access_token: str, refresh_token: str) -> None:
    """
    Insert or update athlete tokens in the database.
    """
    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO tokens (athlete_id, access_token, refresh_token) VALUES (?, ?, ?)",
                (athlete_id, access_token, refresh_token),
            )
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tokens (athlete_id, access_token, refresh_token)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (athlete_id) DO UPDATE SET
                      access_token = EXCLUDED.access_token,
                      refresh_token = EXCLUDED.refresh_token,
                      updated_at = CURRENT_TIMESTAMP;
                    """,
                    (athlete_id, access_token, refresh_token),
                )
        conn.commit()
    finally:
        conn.close()


def save_activity_pg(activity: dict) -> None:
    """
    Insert a single Strava activity into the database.
    Skips duplicates (based on primary key).
    """
    conn = get_conn()
    try:
        fields = {
            "activity_id": activity["id"],
            "athlete_id": activity["athlete"]["id"],
            "name": activity.get("name"),
            "start_date": activity.get("start_date"),
            "distance_mi": activity.get("distance", 0) / 1609.34,
            "moving_time_min": activity.get("moving_time", 0) / 60.0,
            "pace_min_per_mile": None,  # Optional calc below
            "data": activity,
        }

        if fields["distance_mi"] > 0:
            fields["pace_min_per_mile"] = (
                fields["moving_time_min"] / fields["distance_mi"]
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO activities (
                    activity_id, athlete_id, name, start_date,
                    distance_mi, moving_time_min, pace_min_per_mile, data
                ) VALUES (%(activity_id)s, %(athlete_id)s, %(name)s, %(start_date)s,
                          %(distance_mi)s, %(moving_time_min)s, %(pace_min_per_mile)s, %(data)s)
                ON CONFLICT (activity_id) DO NOTHING
                """,
                fields,
            )
        conn.commit()
    finally:
        conn.close()
