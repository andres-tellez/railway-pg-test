# run.py

import os
import sys
from src.app import create_app

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Initialize the Flask app
app = create_app()

# Pull the port from the PORT env var (Railway sets this), default to 8080 for deployment
port = int(os.environ.get("PORT", 8080))

if __name__ == "__main__":
    print(
        f"🚀 Starting app on 0.0.0.0:{port} with DATABASE_URL = {app.config.get('DATABASE_URL')}",
        flush=True,
    )

    # Optional DB connection test
    try:
        from psycopg2 import connect

        conn = connect(app.config["DATABASE_URL"], sslmode="require")
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        print("✅ DB test query succeeded!", flush=True)
    except Exception as e:
        print("⚠️ DB test query failed:", e, flush=True)

    # Start the server (local or hosted)
    app.run(host="0.0.0.0", port=port, debug=True)
