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
from dotenv import load_dotenv
from src.startup_checks import perform_startup_checks
from src.routes.sync_routes import SYNC
from src.routes.auth import auth_bp
from src.routes.enrich import enrich_bp


def create_app(test_config=None):
    """
    Create and configure a Flask application instance.

    Args:
        test_config (dict, optional): Overrides to apply for testing, e.g.,
            {'TESTING': True, 'DATABASE_URL': 'sqlite:///:memory:'}.
    Returns:
        Flask app: A configured Flask application.
    """

    # Load environment variables from .env file into os.environ
    env_path = Path(__file__).resolve().parent.parent / ".env"
    print(f"📄 Looking for .env at: {env_path}", flush=True)
    load_dotenv(dotenv_path=env_path, override=True)

    print("🧪 cwd:", os.getcwd())
    print("🧪 files in cwd:", [p.name for p in Path(".").iterdir()])

    print("💾 DATABASE_URL in app:", os.getenv("DATABASE_URL"))

    if not env_path.exists():
        print("❌ .env file not found!")
    else:
        with open(env_path, encoding="utf-8") as f:
            print("📄 .env contents:")
            print(f.read())

    print("🔐 ADMIN_USER:", os.getenv("ADMIN_USER"))
    print("🔐 ADMIN_PASS:", os.getenv("ADMIN_PASS"))

    # Perform startup sanity checks (env vars, DB connectivity, workflows)
    perform_startup_checks()

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

    # Blueprint registration: auth, enrich, and sync modules
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(enrich_bp, url_prefix="/enrich")
    app.register_blueprint(SYNC)

    # Health check endpoint
    @app.route("/ping")
    def ping():
        """A simple endpoint to verify the app is running."""
        return "pong", 200

    # Database initialization endpoint (defer import of init_db)
    @app.route("/init-db")
    def init_db_route():
        """Initialize or reset the application's database schema."""
        print(
            "🔄 init-db called with DATABASE_URL:",
            app.config["DATABASE_URL"],
            flush=True,
        )
        try:
            from src.db import init_db  # deferred import to avoid circular

            init_db(app.config["DATABASE_URL"])
            print("✅ init_db() completed successfully", flush=True)
            return "Database initialized", 200
        except Exception as e:
            print(f"❌ init_db error: {e}", flush=True)
            return f"Error initializing DB: {e}", 500

    # Debug: list all registered routes for verification
    for rule in app.url_map.iter_rules():
        print(f"🔍 Registered route: {rule.endpoint} -> {rule.rule}", flush=True)

    return app


# Entry point for local development
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Starting app on 0.0.0.0:{port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=True)
