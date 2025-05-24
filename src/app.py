"""
Module: src/app.py
Application factory and core route registration for the Smart Marathon Coach API.

This module defines the create_app() factory that configures the Flask app,
loads environment settings, registers blueprints, and provides basic health
and initialization endpoints.
"""

import os
from pathlib import Path
from flask import Flask
# from dotenv import load_dotenv  # TEMP: Commented out dotenv loading

from src.routes.sync_routes import SYNC
from src.routes.auth import auth_bp
from src.routes.enrich import enrich_bp
from src.routes.tasktracker_routes import tasktracker_bp  # Task tracker blueprint


def create_app(test_config=None):
    """
    Create and configure a Flask application instance.

    Args:
        test_config (dict, optional): Overrides to apply for testing, e.g.,
            {'TESTING': True, 'DATABASE_URL': 'sqlite:///:memory:'}.
    Returns:
        Flask app: A configured Flask application.
    """
    print("✅ ENTERED create_app()", flush=True)

    # TEMP: Disabled .env loading for clean Railway behavior
    # if os.getenv("FLASK_ENV") != "testing":
    #     env_path = Path(__file__).resolve().parent.parent / ".env"
    #     print(f"📄 Looking for .env at: {env_path}", flush=True)
    #     load_dotenv(dotenv_path=env_path, override=True)

    #     print("🧪 cwd:", os.getcwd())
    #     print("🧪 files in cwd:", [p.name for p in Path(".").iterdir()])
    #     print("💾 DATABASE_URL in app:", os.getenv("DATABASE_URL"))

    #     if not env_path.exists():
    #         print("❌ .env file not found!")
    #     else:
    #         with open(env_path, encoding="utf-8") as f:
    #             print("📄 .env contents:")
    #             print(f.read())

    #     print("🔐 ADMIN_USER:", os.getenv("ADMIN_USER"))
    #     print("🔐 ADMIN_PASS:", os.getenv("ADMIN_PASS"))

    # Instantiate the Flask app
    app = Flask(__name__, instance_relative_config=False)

    # Configuration: default settings
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        CRON_SECRET_KEY=os.environ.get("CRON_SECRET_KEY"),
    )

    # Apply any test-specific configuration on top
    if test_config:
        app.config.update(test_config)

    # Blueprint registration
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(enrich_bp, url_prefix="/enrich")
    app.register_blueprint(SYNC)
    app.register_blueprint(tasktracker_bp)

    # Health check endpoint
    @app.route("/ping")
    def ping():
        return "pong", 200

    # DB check endpoint
    @app.route("/db-check")
    def db_check():
        try:
            from psycopg2 import connect
            conn = connect(app.config["DATABASE_URL"], sslmode="disable")
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            return {"status": "ok", "db": True}
        except Exception as e:
            return {"status": "fail", "error": str(e)}, 500

    # Startup diagnostics endpoint
    @app.route("/startup")
    def startup():
        return {
            "status": "started",
            "env_PORT": os.environ.get("PORT"),
            "env_DATABASE_URL": os.environ.get("DATABASE_URL"),
            "config_DATABASE_URL": app.config.get("DATABASE_URL"),
            "cwd": os.getcwd(),
            "files": [p.name for p in Path(".").iterdir()],
        }

    return app
