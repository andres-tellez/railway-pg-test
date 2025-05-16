import os
import sqlite3
import psycopg2
from urllib.parse import urlparse


def init_db(database_url=None):
    """
    Initialize or reset the application's database schema.

    Reads SQL from `schema.sql` at the project root and executes it.
    """
    database_url = database_url or os.environ["DATABASE_URL"]
    parsed = urlparse(database_url)

    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")
    print("🔍 Attempting to open schema at:", schema_path, flush=True)

    with open(schema_path, "r", encoding="utf-8") as f:
        ddl = f.read()

    if database_url.startswith("sqlite"):
        print(f"🔍 Connecting to SQLite at {parsed.path}", flush=True)
        conn = sqlite3.connect(parsed.path)
        try:
            conn.executescript(ddl)
            conn.commit()
            print("✅ init_db() completed successfully", flush=True)
        finally:
            conn.close()
    else:
        print(f"🔍 Connecting to Postgres at {parsed.hostname}", flush=True)
        conn = psycopg2.connect(database_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
            print("✅ init_db() completed successfully", flush=True)
        finally:
            conn.close()
