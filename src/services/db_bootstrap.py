import os
import sqlite3
import psycopg2
from urllib.parse import urlparse


def init_db(database_url=None):
    """
    Initialize or reset the application's database schema.

    Reads SQL from `schema.sql` at the project root and executes it.
    Supports both PostgreSQL and SQLite.
    """
    database_url = database_url or os.environ["DATABASE_URL"]
    parsed = urlparse(database_url)

    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")
    print("🔍 Attempting to open schema at:", schema_path, flush=True)

    with open(schema_path, "r", encoding="utf-8") as f:
        ddl = f.read()

    if database_url.startswith("sqlite"):
        sqlite_path = parsed.path.lstrip("/") if os.name == "nt" else parsed.path
        print(f"🔍 Connecting to SQLite at {sqlite_path}", flush=True)
        conn = sqlite3.connect(sqlite_path)
        try:
            conn.executescript(ddl)
            conn.commit()
            print("✅ init_db() completed successfully", flush=True)
        finally:
            conn.close()
    else:
        # Smart SSL logic: disable for local containers, require for real deployments
        ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1", "db") else "require"
        print(f"🔍 Connecting to Postgres at {parsed.hostname} with sslmode={ssl_mode}", flush=True)
        conn = psycopg2.connect(database_url, sslmode=ssl_mode)
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
            print("✅ init_db() completed successfully", flush=True)
        finally:
            conn.close()


def get_conn():
    """
    Return a live DB connection using DATABASE_URL.
    """
    database_url = os.environ["DATABASE_URL"]
    parsed = urlparse(database_url)
    ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1", "db") else "require"
    return psycopg2.connect(database_url, sslmode=ssl_mode)
