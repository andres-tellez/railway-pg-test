# db.py

import os
import json
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from typing import Dict, Optional, List
from urllib.parse import urlparse

# Load .env when in development
if os.getenv("FLASK_ENV") == "development":
    load_dotenv()


def get_conn():
    if os.getenv("FLASK_ENV") == "development":
        conn = sqlite3.connect("dev.sqlite3")
        conn.row_factory = sqlite3.Row
        return conn

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")

    parsed = urlparse(db_url)
    ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1") else "require"
    conn = psycopg2.connect(db_url, sslmode=ssl_mode)
    with conn.cursor() as cur:
        cur.execute("SET search_path TO public;")
    return conn


def save_token_pg(athlete_id: int, access_token: str, refresh_token: str) -> None:
    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                  athlete_id INTEGER PRIMARY KEY,
                  access_token TEXT NOT NULL,
                  refresh_token TEXT NOT NULL,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                INSERT OR REPLACE INTO tokens (athlete_id, access_token, refresh_token)
                VALUES (?, ?, ?);
            """, (athlete_id, access_token, refresh_token))
        else:
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
        conn.commit()
    finally:
        conn.close()


def get_tokens_pg(athlete_id: int) -> Optional[Dict[str, str]]:
    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute(
                "SELECT access_token, refresh_token FROM tokens WHERE athlete_id = ?",
                (athlete_id,)
            )
            row = cur.fetchone()
            return {"access_token": row[0], "refresh_token": row[1]} if row else None
        else:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT access_token, refresh_token
                    FROM tokens
                    WHERE athlete_id = %s;
                """, (athlete_id,))
                return cur.fetchone()
    finally:
        conn.close()


def save_activity_pg(activity: Dict) -> None:
    activity_id     = activity["id"]
    athlete_id      = activity["athlete"]["id"]
    name            = activity.get("name")
    start_date      = activity.get("start_date_local") or activity.get("start_date")
    distance_m      = activity.get("distance", 0)
    moving_s        = activity.get("moving_time", 0)

    distance_mi     = round(distance_m / 1609.34, 2) if distance_m else 0
    moving_time_min = round(moving_s / 60, 2)    if moving_s else 0
    pace            = round(moving_time_min / distance_mi, 2) if distance_mi and moving_time_min else None
    full_json       = json.dumps(activity)

    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                  activity_id INTEGER PRIMARY KEY,
                  athlete_id INTEGER,
                  name TEXT,
                  start_date TEXT,
                  distance_mi REAL,
                  moving_time_min REAL,
                  pace_min_per_mile REAL,
                  data TEXT
                );
            """)
            cur.execute("""
                INSERT OR IGNORE INTO activities (
                  activity_id, athlete_id, name, start_date,
                  distance_mi, moving_time_min, pace_min_per_mile, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
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
        else:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO activities (
                      activity_id, athlete_id, name, start_date,
                      distance_mi, moving_time_min, pace_min_per_mile, data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
        conn.commit()
    finally:
        conn.close()


def enrich_activity_pg(activity_id: int, detailed_data: Dict) -> None:
    full_json = json.dumps(detailed_data)
    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute("""
                UPDATE activities SET data = ? WHERE activity_id = ?;
            """, (full_json, activity_id))
            conn.commit()
        else:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE activities SET data = %s WHERE activity_id = %s;
                """, (full_json, activity_id))
            conn.commit()
    finally:
        conn.close()


def save_run_splits(activity_id: int, splits: List[Dict]) -> None:
    conn = get_conn()
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS run_splits (
                  activity_id INTEGER,
                  segment_index INTEGER,
                  distance_m REAL,
                  elapsed_time REAL,
                  pace REAL,
                  average_heartrate REAL,
                  PRIMARY KEY(activity_id, segment_index)
                );
            """)
            for s in splits:
                cur.execute("""
                    INSERT OR REPLACE INTO run_splits (
                      activity_id, segment_index, distance_m, elapsed_time, pace, average_heartrate
                    ) VALUES (?, ?, ?, ?, ?, ?);
                """, (
                    activity_id,
                    s["segment_index"],
                    s["distance"],
                    s["elapsed_time"],
                    s["pace"],
                    s.get("average_heartrate")
                ))
            conn.commit()
        else:
            with conn.cursor() as cur:
                for s in splits:
                    cur.execute("""
                        INSERT INTO run_splits (
                          activity_id, segment_index, distance_m, elapsed_time, pace, average_heartrate
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (activity_id, segment_index)
                          DO UPDATE SET
                            elapsed_time      = EXCLUDED.elapsed_time,
                            pace              = EXCLUDED.pace,
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
    finally:
        conn.close()
