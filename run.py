# run.py

import os
import sys
from src.app import create_app

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Only create app once (used by both local and gunicorn)
app = create_app()

if __name__ == "__main__":
    # Local dev only — PORT defaults to 5000
    port = int(os.environ.get("PORT", 5000))
    print(
        f"🚀 Starting app locally on 0.0.0.0:{port} with DATABASE_URL = {app.config.get('DATABASE_URL')}",
        flush=True,
    )

    try:
        from psycopg2 import connect

        conn = connect(app.config["DATABASE_URL"], sslmode="require")
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        print("✅ DB test query succeeded!", flush=True)
    except Exception as e:
        print("⚠️ DB test query failed:", e, flush=True)

    app.run(host="0.0.0.0", port=port, debug=True)
