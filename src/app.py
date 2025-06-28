import os
from dotenv import load_dotenv

# ✅ Load base env to read FLASK_ENV first
load_dotenv(".env", override=False)

# ✅ Load the correct environment file before any config-dependent imports
env_mode = os.getenv("FLASK_ENV", "production")
if env_mode == "test":
    load_dotenv(".env.test", override=True)
elif env_mode == "production":
    load_dotenv(".env.prod", override=True)
else:
    load_dotenv(".env.dev", override=True)

print(f"✅ EARLY dotenv loaded for FLASK_ENV={env_mode}", flush=True)

# ✅ Now it's safe to import things that use env vars
from flask import Flask
import src.utils.config as config
from src.routes.admin_routes import admin_bp
from src.routes.auth_routes import auth_bp
from src.routes.activity_routes import activity_bp
from src.routes.health_routes import health_bp
from src.routes.ask_routes import ask_bp
from pathlib import Path


def create_app(test_config=None):
    print("✅ ENTERED create_app()", flush=True)
    print("📁 CWD:", os.getcwd(), flush=True)
    print("📁 Contents of current working dir:", os.listdir(os.getcwd()), flush=True)

    is_local = os.getenv("IS_LOCAL", "false").lower() == "true"
    print(f"🌍 FLASK_ENV={env_mode} | IS_LOCAL={is_local}", flush=True)

    print("DEBUG ENV VARS:")
    print(f"DATABASE_URL={os.getenv('DATABASE_URL')}", flush=True)

    app = Flask(__name__)

    # Core app configuration
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_URL=os.getenv("DATABASE_URL"),
        CRON_SECRET_KEY=config.CRON_SECRET_KEY,
        INTERNAL_API_KEY=config.INTERNAL_API_KEY,
        SESSION_TYPE="filesystem"
    )

    if test_config:
        app.config.update(test_config)

    print("💾 CONFIG DATABASE_URL (from app.config):", app.config.get("DATABASE_URL"), flush=True)

    # Register routes
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(activity_bp, url_prefix="/sync")
    app.register_blueprint(health_bp)
    app.register_blueprint(ask_bp)

    @app.route("/ping")
    def ping():
        return "pong", 200

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

    @app.route("/db-check")
    def db_check():
        try:
            from sqlalchemy import create_engine, inspect
            db_url = os.getenv("DATABASE_URL")
            print("🧪 /db-check using DB URL:", db_url, flush=True)

            engine = create_engine(db_url)
            insp = inspect(engine)
            columns = insp.get_columns("splits")
            split_col = next((c for c in columns if c["name"] == "split"), None)

            print("🧪 SPLIT COLUMN:", split_col, flush=True)

            return {
                "status": "ok",
                "db": True,
                "split_column": {
                    "name": split_col["name"],
                    "type": str(split_col["type"]),
                    "nullable": split_col["nullable"]
                } if split_col else "not found"
            }
        except Exception as e:
            import traceback
            print("🔥 DB-CHECK EXCEPTION:", flush=True)
            traceback.print_exc()
            return {"status": "fail", "error": str(e)}, 500

    print("✅ Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}", flush=True)

    return app
