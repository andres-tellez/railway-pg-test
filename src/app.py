import os
from pathlib import Path
from flask import Flask

import src.utils.config as config
from src.routes.admin_routes import admin_bp
from src.routes.auth_routes import auth_bp
from src.routes.activity_routes import activity_bp


def create_app(test_config=None):
    print("✅ ENTERED create_app()", flush=True)
    print("📁 CWD:", os.getcwd(), flush=True)
    print("📁 Contents of current working dir:", os.listdir(os.getcwd()), flush=True)

    env_mode = os.getenv("FLASK_ENV", "production")
    is_local = os.getenv("IS_LOCAL", "false").lower() == "true"
    print(f"🌍 FLASK_ENV={env_mode} | IS_LOCAL={is_local}", flush=True)

    print("🔐 ADMIN_USER:", config.ADMIN_USER)
    print("🔐 ADMIN_PASS:", config.ADMIN_PASS)
    print("🔐 STRAVA_CLIENT_ID:", config.STRAVA_CLIENT_ID)
    print("🔐 STRAVA_CLIENT_SECRET:", config.STRAVA_CLIENT_SECRET)
    print("🔐 STRAVA_REDIRECT_URI:", config.STRAVA_REDIRECT_URI)
    print("💾 CONFIG DATABASE_URL:", config.DATABASE_URL)

    templates_path = Path(__file__).resolve().parent.parent / "templates"

    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder=str(templates_path)
    )

    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_URL=config.DATABASE_URL,
        CRON_SECRET_KEY=config.CRON_SECRET_KEY,
        INTERNAL_API_KEY=config.INTERNAL_API_KEY,
    )

    if test_config:
        app.config.update(test_config)

    print("💾 CONFIG DATABASE_URL (from app.config):", app.config.get("DATABASE_URL"))

    # ✅ Register Blueprints with correct prefixes
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(activity_bp, url_prefix="/sync")

    @app.route("/ping")
    def ping():
        return "pong", 200

    @app.route("/db-check")
    def db_check():
        try:
            from psycopg2 import connect
            db_url = config.DATABASE_URL
            print("🧪 /db-check using DB URL:", db_url, flush=True)
            conn = connect(db_url)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
            return {"status": "ok", "db": True}
        except Exception as e:
            import traceback
            print("🔥 DB-CHECK EXCEPTION:", flush=True)
            traceback.print_exc()
            return {"status": "fail", "error": str(e)}, 500

    @app.route("/startup")
    def startup():
        return {
            "status": "started",
            "env_PORT": os.getenv("PORT"),
            "env_DATABASE_URL": os.getenv("DATABASE_URL"),
            "config_DATABASE_URL": config.DATABASE_URL,
            "cwd": os.getcwd(),
            "files": [p.name for p in Path(".").iterdir()],
        }

    print("✅ Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}", flush=True)

    return app
