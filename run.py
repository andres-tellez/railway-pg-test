import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

print("DATABASE_URL at runtime:", os.getenv("DATABASE_URL"), flush=True)

# ─────────────────────────────
# 📦 Load Environment
# ─────────────────────────────
load_dotenv()

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

import src.utils.config as config
from src.db.session import get_db_session
from src.services.ingestion_orchestration_service import run_full_ingestion_and_enrichment

print("📦 Starting run.py...", flush=True)

# ─────────────────────────────
# 🔧 Patch DB URL if needed
# ─────────────────────────────
if config.IS_LOCAL and config.DATABASE_URL and 'postgres@postgres:' in config.DATABASE_URL:
    patched_db_url = config.DATABASE_URL.replace('postgres@postgres:', 'postgres@localhost:')
    os.environ['DATABASE_URL'] = patched_db_url
    print(f"🔧 DATABASE_URL rewritten for local: {patched_db_url}", flush=True)
else:
    print(f"✅ DATABASE_URL used as-is: {config.DATABASE_URL}", flush=True)

# ─────────────────────────────
# ⚙️ CRON Job Mode
# ─────────────────────────────
if __name__ == "__main__" and os.getenv("RUN_CRON") == "true":
    print(f"[CRON SYNC] ✅ Sync job started at {datetime.utcnow().isoformat()}", flush=True)
    try:
        session = get_db_session()
        athlete_id = int(os.getenv("ATHLETE_ID", "123456"))  # Ensure valid ID is set in Railway
        result = run_full_ingestion_and_enrichment(session, athlete_id)
        print(f"[CRON SYNC] ✅ Sync complete: {result}", flush=True)
    except Exception as e:
        print(f"[CRON SYNC] ❌ Error during sync: {e}", flush=True)
        import traceback
        traceback.print_exc()
    sys.exit(0)  # Exit to prevent Flask startup after cron run

# ─────────────────────────────
# 🚀 Normal Flask App Setup
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

# Check template directory
template_dir = Path(__file__).parent / "templates"
if not template_dir.exists():
    print(f"❌ Template folder not found: {template_dir}", flush=True)
else:
    print(f"📂 Template folder contents: {[f.name for f in template_dir.glob('*')]}", flush=True)

if __name__ == "__main__":
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
