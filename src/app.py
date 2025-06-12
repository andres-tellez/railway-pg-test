import os
from pathlib import Path
from flask import Flask

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

    print("🔐 ADMIN_USER:", os.getenv("ADMIN_USER"))
    print("🔐 ADMIN_PASS:", os.getenv("ADMIN_PASS"))
    print("🔐 STRAVA_CLIENT_ID:", os.getenv("STRAVA_CLIENT_ID"))
    print("🔐 STRAVA_CLIENT_SECRET:", os.getenv("STRAVA_CLIENT_SECRET"))
    print("🔐 REDIRECT_URI:", os.getenv("REDIRECT_URI"))
    print("💾 ENV DATABASE_URL:", os.getenv("DATABASE_URL"))

    templates_path = Path(__file__).resolve().parent.parent / "templates"

    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder=str(templates_path)
    )

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        CRON_SECRET_KEY=os.environ.get("CRON_SECRET_KEY"),
        INTERNAL_API_KEY=os.environ.get("INTERNAL_API_KEY"),
    )

    if test_config:
        app.config.update(test_config)

    print("💾 CONFIG DATABASE_URL:", app.config.get("DATABASE_URL"))

    # ✅ Register Blueprints
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
            db_url = app.config.get("DATABASE_URL")
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
            "env_PORT": os.environ.get("PORT"),
            "env_DATABASE_URL": os.environ.get("DATABASE_URL"),
            "config_DATABASE_URL": app.config.get("DATABASE_URL"),
            "cwd": os.getcwd(),
            "files": [p.name for p in Path(".").iterdir()],
        }

    print("✅ Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}", flush=True)

    return app
