"""
Module: src/app.py
Application factory and core route registration for the Smart Marathon Coach API.
"""

import os
from pathlib import Path
from flask import Flask
from dotenv import load_dotenv

from src.routes.sync_routes import SYNC
from src.routes.auth import auth_bp
from src.routes.enrich import enrich_bp
from src.routes.tasktracker_routes import tasktracker_bp


def create_app(test_config=None):
    """
    Create and configure a Flask application instance.
    """
    print("✅ ENTERED create_app()", flush=True)
    print("📁 CWD:", os.getcwd(), flush=True)
    print("📁 Contents of current working dir:", os.listdir(os.getcwd()), flush=True)

    # Load environment variables unless in testing
    if os.getenv("FLASK_ENV") != "testing":
        env_path = Path(__file__).resolve().parent.parent / ".env"
        print(f"📄 Looking for .env at: {env_path}", flush=True)
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            with open(env_path, encoding="utf-8") as f:
                print("📄 .env contents:")
                print(f.read())
        else:
            print("❌ .env file not found!")

    print("🔐 ADMIN_USER:", os.getenv("ADMIN_USER"))
    print("🔐 ADMIN_PASS:", os.getenv("ADMIN_PASS"))
    print("💾 DATABASE_URL in app:", os.getenv("DATABASE_URL"))

    # ✅ Set absolute path to templates to ensure it resolves in production
    templates_path = Path(__file__).resolve().parent.parent / "templates"

    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder=str(templates_path)
    )

    # Config setup
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        CRON_SECRET_KEY=os.environ.get("CRON_SECRET_KEY"),
    )

    if test_config:
        app.config.update(test_config)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(enrich_bp, url_prefix="/enrich")
    app.register_blueprint(SYNC)
    app.register_blueprint(tasktracker_bp)

    # Simple diagnostic endpoints
    @app.route("/ping")
    def ping():
        return "pong", 200

    @app.route("/db-check")
    def db_check():
        try:
            from psycopg2 import connect
            conn = connect(app.config["DATABASE_URL"])
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            return {"status": "ok", "db": True}
        except Exception as e:
            return {"status": "fail", "error": str(e)}, 500

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

    # Debug: List all registered routes
    print("✅ Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}", flush=True)

    return app
