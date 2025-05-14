# db/db.py

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    """Return a new psycopg2 connection using DATABASE_URL from env."""
    db_url = os.getenv("DATABASE_URL")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)
