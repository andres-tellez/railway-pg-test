# run.py

import os
import sys

# Ensure the project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.app import create_app

# If you're in development mode and want SQLite, you can export:
#   $env:FLASK_ENV="development"
#   $env:DATABASE_URL="sqlite:///dev.sqlite3"
# But by default, this just respects your .env or shell.
app = create_app()

if __name__ == "__main__":
    print("🚀 Starting app with DATABASE_URL =", app.config.get("DATABASE_URL"), flush=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
