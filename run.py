# run.py

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("📦 Starting run.py...", flush=True)

# 🔐 Load .env explicitly (important in Docker or if run manually)
load_dotenv()

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Attempt to create the app and log failure explicitly
try:
    from src.app import create_app
    app = create_app()  # 🔑 Gunicorn will reference this: "run:app"
    print("✅ App created via create_app()", flush=True)
except Exception as e:
    print("🔥 App creation failed:", e, flush=True)
    import traceback
    traceback.print_exc()
    raise  # Re-raise so Railway crash logs capture the stack

# CLI mode: run init-db early and exit
if len(sys.argv) > 1 and sys.argv[1] == "init-db":
    from src.db.init_db import init_db
    print("🔧 Running init-db...", flush=True)
    try:
        init_db()
        print("✅ init-db completed successfully", flush=True)
    except Exception as e:
        print("❌ init-db failed:", e, flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)

# Check that templates folder is visible to Flask
template_dir = Path(__file__).parent / "templates"
if not template_dir.exists():
    print(f"❌ Template folder not found: {template_dir}")
else:
    print(f"📂 Template folder contents: {[f.name for f in template_dir.glob('*')]}")

# If run directly, use Flask dev server
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))

    # 🔍 Full environment debug
    env_db_url = os.environ.get("DATABASE_URL")
    config_db_url = app.config.get("DATABASE_URL") or env_db_url
    print("🔍 ENV DATABASE_URL =", env_db_url, flush=True)
    print("🔍 CONFIG DATABASE_URL =", config_db_url, flush=True)

    if not config_db_url:
        print("❗ DATABASE_URL not set — exiting", flush=True)
        sys.exit(1)

    try:
        from psycopg2 import connect
        print(f"🔌 Attempting psycopg2.connect() to: {config_db_url}", flush=True)
        conn = connect(config_db_url)
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
