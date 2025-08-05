# validate_envs.py

import os
from dotenv import load_dotenv
import psycopg2

REQUIRED_KEYS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "STRAVA_REDIRECT_URI",
    "ADMIN_USER",
    "ADMIN_PASS",
    "CRON_SECRET_KEY",
    "INTERNAL_API_KEY",
    "ACCESS_TOKEN_EXP",
    "REFRESH_TOKEN_EXP",
    "ATHLETE_ID",
]

ENV_FILES = {"development": ".env", "test": ".env.test", "production": ".env.prod"}


def validate_env(env_name, env_file):
    print(f"\nValidating {env_name.upper()} ({env_file})")
    load_dotenv(dotenv_path=env_file, override=True)

    # Check keys
    missing = [key for key in REQUIRED_KEYS if not os.getenv(key)]
    if missing:
        print(f"❌ Missing keys: {missing}")
    else:
        print("✅ All required keys present")

    # DB Connection Test
    db_url = os.getenv("DATABASE_URL")

    # Sanitize for psycopg2
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        print("✅ Database connection successful")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")


if __name__ == "__main__":
    for name, path in ENV_FILES.items():
        validate_env(name, path)
