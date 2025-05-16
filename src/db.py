"""
Module: src/db.py
Database connection and initialization helpers for Smart Marathon Coach.

Provides:
- `get_conn(database_url)`: Acquire a DB connection (SQLite or Postgres) based on environment.
- `init_db(database_url)`: Initialize or reset the database schema from `schema.sql`.
- Token persistence & retrieval functions.
"""

import os
import sqlite3
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor

import time


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


def init_db(database_url=None):
    """
    Initialize or reset the application's database schema.

    Reads SQL from `schema.sql` at the project root and executes it.
    """
    conn = get_conn()
    try:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
        print("🔍 Attempting to open schema at:", schema_path, flush=True)
        with open(schema_path, "r") as f:
            ddl = f.read()

        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.executescript(ddl)
        else:
            with conn.cursor() as cur:
                cur.execute(ddl)

        conn.commit()
        print("✅ init_db() completed successfully", flush=True)
    except Exception as e:
        print(f"❌ init_db error: {e}", flush=True)
        raise
    finally:
        conn.close()


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
