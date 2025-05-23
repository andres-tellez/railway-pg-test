import sqlite3
import uuid
from pathlib import Path


def test_db_schema_bootstrap(tmp_path):
    # Use a standalone SQLite file
    db_path = tmp_path / f"{uuid.uuid4().hex}.sqlite3"
    schema_path = Path("schema.sql")

    assert schema_path.exists(), "Missing schema.sql at project root"

    # Load the schema.sql
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = f.read()

    # Create schema and run test in pure SQLite
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        conn.executescript(schema)
        conn.execute(
            "INSERT INTO tokens (athlete_id, access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?)",
            ("test123", "abc", "def", 999999),
        )
        rows = conn.execute("SELECT * FROM tokens").fetchall()
        assert len(rows) == 1
    finally:
        conn.close()
