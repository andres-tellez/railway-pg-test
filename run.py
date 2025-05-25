# run.py

import os
import sys

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# CLI mode: run init-db early and exit
if len(sys.argv) > 1 and sys.argv[1] == "init-db":
    from src.db.init_db import init_db  # ✅ Correct function import
    print("🔧 Running init-db...", flush=True)
    init_db()
    sys.exit(0)

# Default path: start Flask app
from src.app import create_app
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))

    print(
        f"🚀 Starting app locally on 0.0.0.0:{port} with DATABASE_URL = {app.config.get('DATABASE_URL')}",
        flush=True,
    )

    try:
        from psycopg2 import connect
        conn = connect(app.config["DATABASE_URL"])
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        print("✅ DB test query succeeded!", flush=True)
    except Exception as e:
        print("⚠️ DB test query failed:", e, flush=True)

    app.run(host="0.0.0.0", port=port, debug=True)
