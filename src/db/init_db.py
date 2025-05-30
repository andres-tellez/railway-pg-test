import os
import psycopg2
from sqlalchemy import create_engine, text
from src.core import get_engine
from src.db.models.tokens import Base as TokensBase
from src.db.models.activities import Base as ActivitiesBase

def get_conn(db_url=None):
    """
    Return a low-level database connection.
    Uses PostgreSQL if the URL is set.
    """
    db_url = db_url or os.getenv("DATABASE_URL") or (current_app.config.get("DATABASE_URL") if current_app else None)
    
    if db_url is None:
        raise RuntimeError("DATABASE_URL is not set!")

    parsed = urlparse(db_url)

    if db_url.startswith("sqlite"):
        path = parsed.path.lstrip("/") if os.name == "nt" else parsed.path
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        if current_app and not current_app.config.get("TESTING") and hasattr(g, "db_conn"):
            return g.db_conn
        if current_app:
            g.db_conn = conn
        return conn
    else:
        ssl_mode = "disable" if parsed.hostname in ("localhost", "127.0.0.1", "db") else "require"
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

    # ✅ Load raw schema.sql
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

    # ✅ ORM tables
    TokensBase.metadata.create_all(bind=engine)
    ActivitiesBase.metadata.create_all(bind=engine)
    # Removed reference to RunSplitsBase as the table is deleted
    print("✅ ORM models initialized successfully", flush=True)
