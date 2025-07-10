import os
from dotenv import load_dotenv
from pathlib import Path

# 📦 Environment Setup
raw_env_mode = os.environ.get("FLASK_ENV", "production")
env_path = {
    "test": ".env.test",
    "staging": ".env.staging",
    "production": ".env.prod"
}.get(raw_env_mode, ".env")

load_dotenv(env_path, override=True)
print(f"✅ Loaded environment: {env_path}", flush=True)

if env_path != ".env":
    print("🚫 Skipping .env fallback", flush=True)
else:
    print("ℹ️ Default .env used", flush=True)

print(f"📍 STRAVA_REDIRECT_URI = {os.getenv('STRAVA_REDIRECT_URI')}", flush=True)

# 🌐 Flask Setup
from flask import Flask, send_from_directory, redirect
from flask_cors import CORS
import src.utils.config as config
from src.routes.admin_routes import admin_bp
from src.routes.auth_routes import auth_bp
from src.routes.activity_routes import activity_bp
from src.routes.health_routes import health_bp
from src.routes.ask_routes import ask_bp

def create_app(test_config=None):
    app = Flask(__name__, static_folder="static", static_url_path="/")
    CORS(app, supports_credentials=True)

    # 🔐 Configuration
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_URL=os.getenv("DATABASE_URL"),
        CRON_SECRET_KEY=config.CRON_SECRET_KEY,
        INTERNAL_API_KEY=config.INTERNAL_API_KEY,
        SESSION_TYPE="filesystem"
    )

    if test_config:
        app.config.update(test_config)

    # 🔗 Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(activity_bp, url_prefix="/sync")
    app.register_blueprint(health_bp)
    app.register_blueprint(ask_bp)

    # 🧪 Utility Endpoints
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
            engine = create_engine(db_url)
            insp = inspect(engine)
            columns = insp.get_columns("splits")
            split_col = next((c for c in columns if c["name"] == "split"), None)
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
            traceback.print_exc()
            return {"status": "fail", "error": str(e)}, 500

    @app.route("/post-oauth")
    def post_oauth():
        env = os.getenv("FLASK_ENV", "production")
        if env in ["development", "test"]:
            redirect_url = os.getenv("FRONTEND_REDIRECT")
            return redirect(redirect_url)
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        return "❌ Frontend not found", 404

    @app.errorhandler(404)
    def spa_fallback(e):
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        return "404 Not Found", 404

    return app

# 👟 Local dev only (use `flask run` in prod/staging)
if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000)
