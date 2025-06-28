import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# ─────────────────────────────
# 📦 Setup
# ─────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Check and print the FLASK_ENV to confirm it's being set correctly
env_mode = os.getenv("FLASK_ENV", "production")  # Default to production if FLASK_ENV is not set
print(f"🌍 FLASK_ENV is set to: {env_mode}", flush=True)

# Load environment variables based on FLASK_ENV
if env_mode == "test":
    load_dotenv(".env.test", override=True)
    print("🔍 Loading .env.test for testing", flush=True)
elif env_mode == "development":
    load_dotenv(".env", override=True)
    print("🔍 Loading .env for development", flush=True)
else:
    load_dotenv(".env.prod", override=True)
    print("🔍 Loading .env.prod for production", flush=True)

    
    
    
    

print("DATABASE_URL at runtime:", os.getenv("DATABASE_URL"), flush=True)

import src.utils.config as config
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import run_full_ingestion_and_enrichment

# ─────────────────────────────
# 🚀 Flask App Setup for Gunicorn
# ─────────────────────────────
try:
    from src.app import create_app
    app = create_app()
    print("✅ App created via create_app()", flush=True)
except Exception as e:
    print("🔥 App creation failed:", e, flush=True)
    import traceback
    traceback.print_exc()
    raise

# ─────────────────────────────
# 🧪 Local + Cron Execution Only
# ─────────────────────────────
if __name__ == "__main__":
    print("📦 Starting run.py...", flush=True)

    # Patch DB URL if running locally
    if config.IS_LOCAL and config.DATABASE_URL and 'postgres@postgres:' in config.DATABASE_URL:
        patched_db_url = config.DATABASE_URL.replace('postgres@postgres:', 'postgres@localhost:')
        os.environ['DATABASE_URL'] = patched_db_url
        print(f"🔧 DATABASE_URL rewritten for local: {patched_db_url}", flush=True)
    else:
        print(f"✅ DATABASE_URL used as-is: {config.DATABASE_URL}", flush=True)

    # Run as CRON job if enabled
    if os.getenv("RUN_CRON") == "true":
        print(f"[CRON SYNC] ✅ Sync job started at {datetime.utcnow().isoformat()}", flush=True)
        try:
            session = get_session()
            athlete_id = int(os.getenv("ATHLETE_ID", "123456"))
            result = run_full_ingestion_and_enrichment(session, athlete_id)
            print(f"[CRON SYNC] ✅ Sync complete: {result}", flush=True)
        except Exception as e:
            print(f"[CRON SYNC] ❌ Error during sync: {e}", flush=True)
            import traceback
            traceback.print_exc()
        sys.exit(0)

    # Dev mode — test DB connection and run server
    port = config.PORT
    config_db_url = app.config.get("DATABASE_URL") or config.DATABASE_URL
    print("🔍 ENV DATABASE_URL =", config.DATABASE_URL, flush=True)
    print("🔍 CONFIG DATABASE_URL =", config_db_url, flush=True)

    if not config_db_url:
        print("❗ DATABASE_URL not set — exiting", flush=True)
        sys.exit(1)

    try:
        from psycopg2 import connect
        print(f"🔌 Attempting psycopg2.connect() to: {config_db_url}", flush=True)
        sanitized_url = config_db_url.replace("postgresql+psycopg2://", "postgresql://").split("#")[0].strip()
        conn = connect(sanitized_url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        print("✅ DB test query succeeded!", flush=True)
    except Exception as e:
        print("⚠️ DB test query failed:", e, flush=True)
        import traceback
        traceback.print_exc()


    print(f"🚀 Starting app locally on 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True)
