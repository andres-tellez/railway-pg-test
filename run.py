# run.py

import os
import sys

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.app import create_app

# If you're in development mode and want SQLite, you can export:
#   $env:FLASK_ENV="development"
#   $env:DATABASE_URL="sqlite:///dev.sqlite3"
# But by default, this just respects your shell or Railway’s injected vars.
app = create_app()

if __name__ == "__main__":
    # Pull the port from the PORT env var (Railway sets this), default to 5000 locally
    port = int(os.environ.get("PORT", 5000))
    print(
        f"🚀 Starting app on 0.0.0.0:{port} with DATABASE_URL = {app.config.get('DATABASE_URL')}",
        flush=True,
    )
    app.run(host="0.0.0.0", port=port, debug=True)
