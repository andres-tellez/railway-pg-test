import os
import psycopg2
from urllib.parse import urlparse
from src.db.db_session import get_engine  # ✅ Correct import for unified engine creation
from src.db.models.tokens import Base as TokensBase
from src.db.models.activities import Base as ActivitiesBase


def get_conn(db_url=None):
    """
    Return a low-level database connection.
    Uses PostgreSQL if the URL is set.
    """
    db_url = db_url or os.getenv("DATABASE_URL")

    if db_url is None:
        raise RuntimeError("DATABASE_URL is not set!")

    parsed = urlparse(db_url)

    # Only PostgreSQL supported (SQLite fallback not required)
    ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1", "db", "postgres") else "require"
    conn = psycopg2.connect(
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port,
        sslmode=ssl_mode
    )
    return conn


def init_db(db_url=None):
    """
    Initialize the database schema using ORM models.
    This should only be used for local development and tests.
    Production systems should use Alembic migrations.
    """
    engine = get_engine(db_url)

    print("⚠️ Running ORM-based init_db() — intended for local dev & pytest only.", flush=True)

    TokensBase.metadata.create_all(bind=engine)
    ActivitiesBase.metadata.create_all(bind=engine)

    print("✅ ORM models initialized successfully", flush=True)
