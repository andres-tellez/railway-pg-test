# run.py

import os
import sys

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.app import create_app

app = create_app()

if __name__ == "__main__":
    # Pull the port from the PORT env var (Railway sets this), default to 5000 locally
    port = int(os.environ.get("PORT", 8080))
    print(
        f"🚀 Starting app on 127.0.0.1:{port} with DATABASE_URL = {app.config.get('DATABASE_URL')}",
        flush=True,
    )

    # ==== DB CONNECTION TEST ====
    from psycopg2 import connect, OperationalError

    try:
        conn = connect(app.config["DATABASE_URL"], sslmode="require")
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.fetchone()
        print("✅ DB test query succeeded!", flush=True)
        cur.close()
        conn.close()
    except OperationalError as e:
        print("⚠️ DB test query failed (connectivity issue):", e, flush=True)
        # don’t exit—allow the HTTP server to start so we can test connectivity

    # Start the Flask development server for local use
    app.run(host="0.0.0.0", port=port, debug=True)
