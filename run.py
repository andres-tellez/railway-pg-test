# run.py

import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# -----------------------------------------
# Path Setup
# -----------------------------------------
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))  # For run.py-local imports
sys.path.insert(0, str(src_path))  # Ensures `import src...` works!

# Load env vars before importing config
env_path = Path(".env.local")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print("[OK] Explicitly loaded .env.local", flush=True)
else:
    env_mode = os.getenv("FLASK_ENV", "production")
    env_file = {
        "local": ".env.local",
        "staging": ".env.staging",
        "production": ".env.prod",
    }.get(env_mode, ".env")

    load_dotenv(env_file, override=False)
    print(f"Loaded fallback environment file: {env_file}", flush=True)

print("STRAVA_REDIRECT_URI =", os.getenv("STRAVA_REDIRECT_URI"), flush=True)
print("DATABASE_URL at runtime:", os.getenv("DATABASE_URL"), flush=True)

# Import config AFTER env vars are loaded
from src.utils.config import config

# -----------------------------------------
# Imports
# -----------------------------------------
from src.db.db_session import get_session
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)
from src.app import create_app

# -----------------------------------------
# Flask App Setup for Gunicorn
# -----------------------------------------
app = create_app()
print("App created via create_app()", flush=True)

# -----------------------------------------
# Local + Cron Execution Only
# -----------------------------------------
if __name__ == "__main__":
    print("Starting run.py...", flush=True)

    # Patch DATABASE_URL for local dev if necessary
    if (
        config.IS_LOCAL
        and config.DATABASE_URL
        and "postgres@postgres:" in config.DATABASE_URL
    ):
        patched_db_url = config.DATABASE_URL.replace(
            "postgres@postgres:", "postgres@localhost:"
        )
        os.environ["DATABASE_URL"] = patched_db_url
        print(f"[DEBUG] DATABASE_URL rewritten for local: {patched_db_url}", flush=True)
    else:
        print(f"[OK] DATABASE_URL used as-is: {config.DATABASE_URL}", flush=True)

    # Cron-only mode
    if os.getenv("RUN_CRON") == "true":
        print(
            f"[CRON SYNC] [OK] Sync job started at {datetime.utcnow().isoformat()}",
            flush=True,
        )
        try:
            session = get_session()
            athlete_id = int(os.getenv("ATHLETE_ID", "123456"))
            result = run_full_ingestion_and_enrichment(session, athlete_id)
            print(f"[CRON SYNC] [OK] Sync complete: {result}", flush=True)
        except Exception as e:
            print(f"[CRON SYNC] [ERROR] Error during sync: {e}", flush=True)
            import traceback

            traceback.print_exc()
        sys.exit(0)

    # Local run - automatically handle Railway interference
    railway_port = os.environ.get("PORT")
    if railway_port and railway_port != "5000":
        print(
            f"[INFO] Railway CLI detected (PORT={railway_port}) - auto-fixing for local development",
            flush=True,
        )
        # Clear Railway environment variables that might interfere
        railway_vars = [
            "PORT",
            "RAILWAY_PROJECT_ID",
            "RAILWAY_SERVICE_NAME",
            "RAILWAY_ENVIRONMENT",
        ]
        for var in railway_vars:
            if var in os.environ:
                del os.environ[var]
        print(f"[INFO] Cleared Railway environment variables", flush=True)

    port = 5000
    print(f"[INFO] Starting backend on port {port} for local development", flush=True)

    config_db_url = app.config.get("DATABASE_URL") or config.DATABASE_URL
    print("[DEBUG] ENV DATABASE_URL =", config.DATABASE_URL, flush=True)
    print("[DEBUG] CONFIG DATABASE_URL =", config_db_url, flush=True)

    if not config_db_url:
        print("[ERROR] DATABASE_URL not set — exiting", flush=True)
        sys.exit(1)

    # DB sanity check
    try:
        from psycopg2 import connect

        print(f"[DEBUG] Attempting psycopg2.connect() to: {config_db_url}", flush=True)
        sanitized_url = (
            config_db_url.replace("postgresql+psycopg2://", "postgresql://")
            .split("#")[0]
            .strip()
        )
        conn = connect(sanitized_url)
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        print("[OK] DB test query succeeded!", flush=True)
    except Exception as e:
        print("[WARNING] DB test query failed:", e, flush=True)
        import traceback

        traceback.print_exc()

    # HTTPS support via mkcert (localhost.pem / localhost-key.pem)
    cert_file = os.path.join(os.getcwd(), "localhost.pem")
    key_file = os.path.join(os.getcwd(), "localhost-key.pem")
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print(
            f"[INFO] Running with HTTPS using mkcert: {cert_file}, {key_file}",
            flush=True,
        )
        try:
            import ssl

            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(cert_file, key_file)
            print("[INFO] SSL context created successfully", flush=True)
        except Exception as e:
            print(
                f"[WARNING] Failed to create SSL context: {e}, falling back to tuple format",
                flush=True,
            )
            ssl_context = (cert_file, key_file)
    else:
        print(
            "[WARNING] No mkcert certs found, running without HTTPS (HTTP only)",
            flush=True,
        )
        ssl_context = None

    print(f"[INFO] Starting app locally on 0.0.0.0:{port}", flush=True)
    app.run(
        host="0.0.0.0",
        port=port,
        debug=True,
        ssl_context=ssl_context,
    )
