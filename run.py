# run.py

import os
import sys
from pathlib import Path

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Load and expose the app for Gunicorn
from src.app import create_app
app = create_app()  # 🔑 Gunicorn will reference this: "run:app"

# CLI mode: run init-db early and exit
if len(sys.argv) > 1 and sys.argv[1] == "init-db":
    from src.db.init_db import init_db
    print("🔧 Running init-db...", flush=True)
    init_db()
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
    config_db_url = app.config.get("DATABASE_URL")
    print("🔍 ENV DATABASE_URL =", env_db_url, flush=True)
    print("🔍 CONFIG DATABASE_URL =", config_db_url, flush=True)

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

    print(f"🚀 Starting app locally on 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True)
