import os
from dotenv import load_dotenv

# Load .env variables automatically
load_dotenv()

# Pull DATABASE_URL early
env_db_url = os.environ.get("DATABASE_URL")
is_local = os.environ.get("IS_LOCAL", "false").lower() == "true"
in_docker = os.path.exists('/.dockerenv') or os.environ.get("IN_DOCKER", "false").lower() == "true"

# Step 1 — Rewrite DATABASE_URL depending on environment
if env_db_url:
    patched_db_url = env_db_url

    # Docker Compose case: container hostname replacement
    if in_docker and "localhost" in env_db_url:
        patched_db_url = env_db_url.replace("localhost", "postgres")
        os.environ['DATABASE_URL'] = patched_db_url
        print(f"🔧 DATABASE_URL rewritten for Docker Compose: {patched_db_url}")

    # Local mode with Docker aliases
    elif is_local:
        if '@postgres:' in env_db_url:
            patched_db_url = env_db_url.replace('@postgres:', '@localhost:')
            os.environ['DATABASE_URL'] = patched_db_url
            print(f"🔧 DATABASE_URL rewritten for local Docker (postgres alias): {patched_db_url}")
        elif '@db:' in env_db_url:
            patched_db_url = env_db_url.replace('@db:', '@localhost:')
            os.environ['DATABASE_URL'] = patched_db_url
            print(f"🔧 DATABASE_URL rewritten for local Docker (db alias): {patched_db_url}")
        else:
            print(f"✅ DATABASE_URL used for local development: {patched_db_url}")

    else:
        os.environ['DATABASE_URL'] = patched_db_url
        print(f"✅ DATABASE_URL used as-is: {patched_db_url}")

# Step 2 — SQLAlchemy dialect normalization for psycopg2
patched_db_url = os.environ.get("DATABASE_URL")
if patched_db_url and patched_db_url.startswith("postgresql+psycopg2://"):
    patched_db_url = patched_db_url.replace("postgresql+psycopg2://", "postgresql://")
    os.environ['DATABASE_URL'] = patched_db_url
    print(f"🔧 DATABASE_URL normalized for psycopg2: {patched_db_url}")

# Final output for verification
final_db_url = os.environ.get("DATABASE_URL")
print(f"🔍 Final DATABASE_URL: {final_db_url}")
