# src/db/legacy_sql.py

import os
import psycopg2
import sqlite3

def get_conn(db_url=None):
    """Establishes a connection using DATABASE_URL (Postgres or SQLite)."""
    url = db_url or os.getenv("DATABASE_URL", "sqlite:///dev.sqlite3")

    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        return sqlite3.connect(path)

    if url.startswith("postgresql://"):
        return psycopg2.connect(url)

    raise ValueError("Unsupported DATABASE_URL format")
