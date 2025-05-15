import os
import sys
import pathlib
from psycopg2 import sql, OperationalError
from src.db import get_conn

REQUIRED_ENVS = [
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "DATABASE_URL",
]

REQUIRED_TABLES = ["tokens", "activities", "run_splits"]


def perform_startup_checks():
    # 1) Env-var validation
    missing_envs = [v for v in REQUIRED_ENVS if not os.getenv(v)]
    if missing_envs:
        print(f"❌ Missing required env vars: {', '.join(missing_envs)}")
        sys.exit(1)

    # 2) Quick DB & schema check
    try:
        conn = get_conn()
        cur = conn.cursor()
        db_url = os.getenv("DATABASE_URL", "")

        if "sqlite" in db_url:
            # SQLite version of the check
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            found = {row[0] for row in cur.fetchall()}
        else:
            # Postgres version
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename = ANY(%s)",
                (REQUIRED_TABLES,),
            )
            found = {row[0] for row in cur.fetchall()}

        missing_tables = set(REQUIRED_TABLES) - found
        if missing_tables:
            print(f"❌ Missing DB tables: {', '.join(missing_tables)}")
            sys.exit(1)

        cur.close()
    except OperationalError as e:
        print("❌ Cannot connect to the database:", e)
        sys.exit(1)

    # 3) GitHub Actions check
    workflows = pathlib.Path(".github/workflows")
    if not (workflows.exists() and any(workflows.iterdir())):
        print("❌ .github/workflows folder missing or empty")
        sys.exit(1)

    print("✅ Startup checks passed.")
