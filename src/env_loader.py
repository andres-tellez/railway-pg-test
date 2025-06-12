import os
from dotenv import load_dotenv

# Load .env variables automatically
load_dotenv()

is_local = os.environ.get("IS_LOCAL", "false").lower() == "true"
in_docker = os.path.exists('/.dockerenv') or os.environ.get("IN_DOCKER", "false").lower() == "true"

# Step 1 — Force DATABASE_URL if not set
env_db_url = os.environ.get("DATABASE_URL")

if not env_db_url:
    if in_docker:
        env_db_url = "postgresql+psycopg2://smartcoach:devpass@postgres:5432/smartcoach"
    else:
        env_db_url = "postgresql+psycopg2://smartcoach:devpass@localhost:15432/smartcoach"

    os.environ["DATABASE_URL"] = env_db_url
    print(f"🔧 DATABASE_URL defaulted: {env_db_url}")

# Step 2 — Normalize psycopg2
patched_db_url = os.environ["DATABASE_URL"]
if patched_db_url.startswith("postgresql+psycopg2://"):
    patched_db_url = patched_db_url.replace("postgresql+psycopg2://", "postgresql://")
    os.environ["DATABASE_URL"] = patched_db_url
    print(f"🔧 DATABASE_URL normalized for psycopg2: {patched_db_url}")

# Final confirmation
print(f"🔍 Final DATABASE_URL: {os.environ['DATABASE_URL']}")
