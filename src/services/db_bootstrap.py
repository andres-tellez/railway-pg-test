import os
import sqlite3
from src.db import get_conn


def init_db(database_url=None):
    """
    Initialize or reset the application's database schema.

    Reads SQL from `schema.sql` at the project root and executes it.
    """
    conn = get_conn()
    try:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")
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
