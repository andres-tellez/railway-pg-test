import os
import sys
import pathlib
from psycopg2 import OperationalError

REQUIRED_ENVS = ["STRAVA_CLIENT_ID", "STRAVA_CLIENT_SECRET", "DATABASE_URL"]
REQUIRED_TABLES = ["tokens", "activities", "run_splits"]


def perform_startup_checks():
    # 1) Env‐var validation
    missing = [v for v in REQUIRED_ENVS if not os.getenv(v)]
    if missing:
        print(f"❌ Missing required env vars: {', '.join(missing)}")
        sys.exit(1)

    # 2) DB connectivity & schema check
    try:
        # defer import to break cycle
        from src.db import get_conn

        conn = get_conn()
        cur = conn.cursor()
        db_url = os.getenv("DATABASE_URL", "")
        if "sqlite" in db_url:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            found = {r[0] for r in cur.fetchall()}
        else:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename = ANY(%s)",
                (REQUIRED_TABLES,),
            )
            found = {r[0] for r in cur.fetchall()}

        missing_tables = set(REQUIRED_TABLES) - found
        if missing_tables:
            print(f"⚠️ Missing DB tables (skipped): {', '.join(missing_tables)}")

        cur.close()
        conn.close()

    except OperationalError as e:
        print("❌ Cannot connect to the database:", e)
        sys.exit(1)
    except ImportError as e:
        print(f"❌ DB module import failed: {e}")
        sys.exit(1)

    # 3) GitHub workflows check
    wf = pathlib.Path(".github/workflows")
    if not (wf.exists() and any(wf.iterdir())):
        print("❌ .github/workflows folder missing or empty")
        sys.exit(1)

    print("✅ Startup checks passed.")
