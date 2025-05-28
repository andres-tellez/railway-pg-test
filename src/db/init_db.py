import os
import sqlite3
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import current_app, g


def get_conn(db_url=None):
    # 🔍 Show source of DATABASE_URL
    print("🧪 DEBUG: current_app exists:", bool(current_app))
    print("🧪 DEBUG: current_app.config.get('DATABASE_URL'):", current_app.config.get("DATABASE_URL") if current_app else None)
    print("🧪 DEBUG: os.environ.get('DATABASE_URL'):", os.environ.get("DATABASE_URL"))
    db_url = db_url or os.getenv("DATABASE_URL") or (current_app.config.get("DATABASE_URL") if current_app else None)
    print(f"🧪 DEBUG: get_conn using DATABASE_URL = {db_url}", flush=True)

    if not db_url:
        raise RuntimeError("DATABASE_URL is not set!")

    parsed = urlparse(db_url)

    if db_url.startswith("sqlite"):
        path = parsed.path.lstrip("/") if os.name == "nt" else parsed.path
        print(f"🔍 Connecting to SQLite at {path}", flush=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        if current_app and not current_app.config.get("TESTING") and hasattr(g, "db_conn"):
            return g.db_conn
        if current_app:
            g.db_conn = conn
        print("✅ SQLite connection established", flush=True)
        return conn

    if "sslmode=" not in db_url:
        ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1", "db") else "require"
        db_url += ("&" if "?" in db_url else "?") + f"sslmode={ssl_mode}"

    print(f"🔍 Connecting to Postgres at {parsed.hostname}:{parsed.port}", flush=True)
    conn = psycopg2.connect(dsn=db_url, connect_timeout=5)
    print("✅ Postgres connection established", flush=True)

    with conn.cursor() as cur:
        cur.execute("SET search_path TO public;")
    return conn


def get_tokens_pg(athlete_id: int, db_url=None):
    conn = get_conn(db_url)
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute("SELECT access_token, refresh_token FROM tokens WHERE athlete_id = ?", (athlete_id,))
            row = cur.fetchone()
            return {"access_token": row[0], "refresh_token": row[1]} if row else None

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT access_token, refresh_token FROM tokens WHERE athlete_id = %s", (athlete_id,))
            return cur.fetchone()
    finally:
        if not isinstance(conn, sqlite3.Connection):
            conn.close()


def save_tokens_pg(athlete_id: int, access_token: str, refresh_token: str, db_url=None) -> None:
    conn = get_conn(db_url)
    try:
        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO tokens (athlete_id, access_token, refresh_token)
                VALUES (?, ?, ?)
                """,
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
                      refresh_token = EXCLUDED.refresh_token;
                    """,
                    (athlete_id, access_token, refresh_token),
                )
        conn.commit()
    finally:
        if not isinstance(conn, sqlite3.Connection):
            conn.close()


def save_activity_pg(activity: dict, db_url=None) -> None:
    conn = get_conn(db_url)
    try:
        fields = {
            "activity_id": activity["id"],
            "athlete_id": activity["athlete"]["id"],
            "name": activity.get("name"),
            "start_date": activity.get("start_date"),
            "distance_mi": activity.get("distance", 0) / 1609.34,
            "moving_time_min": activity.get("moving_time", 0) / 60.0,
            "pace_min_per_mile": None,
            "data": activity,
        }

        if fields["distance_mi"] > 0:
            fields["pace_min_per_mile"] = fields["moving_time_min"] / fields["distance_mi"]

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
        if not isinstance(conn, sqlite3.Connection):
            conn.close()


def init_db(db_url=None):
    db_url = db_url or (current_app.config.get("DATABASE_URL") if current_app else None) or os.getenv("DATABASE_URL")
    print(f"🧪 DEBUG: init_db using DATABASE_URL = {db_url}", flush=True)
    conn = get_conn(db_url)
    try:
        schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "schema.sql")
        print("📄 Loading schema from:", schema_path, flush=True)
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        statements = [stmt.strip() for stmt in sql_script.strip().split(";") if stmt.strip()]

        if isinstance(conn, sqlite3.Connection):
            cur = conn.cursor()
            for stmt in statements:
                print(f"📄 Executing:\n{stmt[:80]}...", flush=True)
                cur.execute(stmt + ";")
        else:
            with conn.cursor() as cur:
                for stmt in statements:
                    print(f"📄 Executing:\n{stmt[:80]}...", flush=True)
                    cur.execute(stmt + ";")

        conn.commit()
        print("✅ Database schema created successfully", flush=True)
    finally:
        if not isinstance(conn, sqlite3.Connection):
            conn.close()
