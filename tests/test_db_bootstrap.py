import os
import sqlite3
from src.services.db_bootstrap import init_db
from src.db import get_conn


def test_db_schema_bootstrap(tmp_path):
    test_db = tmp_path / "test.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

    # Re-init schema
    init_db()

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tokens (athlete_id, access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?)",
            ("test123", "abc", "def", 999999),
        )
        cursor.execute("SELECT * FROM tokens")
        rows = cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "test123"
