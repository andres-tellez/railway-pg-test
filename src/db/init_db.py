import os
import psycopg2
from sqlalchemy import text
from urllib.parse import urlparse
from src.db.db_session import get_engine  # ✅ Corrected import to use unified db_session
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

    # Only PostgreSQL supported (SQLite fallback not required in your production stack)
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
    engine = get_engine(db_url)

    # ✅ Load raw schema.sql (runs any DDL you have in that file)
    schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql"))
    print("📄 Loading schema from:", schema_path, flush=True)
    
    with engine.connect() as conn:
        with open(schema_path, "r", encoding="utf-8") as f:
            sql_script = f.read()
        statements = [stmt.strip() for stmt in sql_script.strip().split(";") if stmt.strip()]
        for stmt in statements:
            print(f"📄 Executing:\n{stmt[:80]}...", flush=True)
            conn.execute(text(stmt))
        conn.commit()

    print("✅ Raw schema loaded", flush=True)

    # ✅ ORM tables creation (matches your models exactly)
    TokensBase.metadata.create_all(bind=engine)
    ActivitiesBase.metadata.create_all(bind=engine)

    print("✅ ORM models initialized successfully", flush=True)
