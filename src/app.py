import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse

# 📦 Environment Setup
raw_env_mode = os.environ.get("FLASK_ENV", "production")
env_path = {
    "local": ".env.local",
    "staging": ".env.staging",
    "production": ".env.prod"
}.get(raw_env_mode, ".env")

load_dotenv(env_path, override=False)
print(f"🔍 Loaded environment file: {env_path}", flush=True)

# ⛏️ Patch for Railway proxy handling
original_url = os.getenv("DATABASE_URL", "")
parsed = urlparse(original_url)
if "proxy.rlwy.net" in parsed.hostname:
    os.environ["DATABASE_URL"] = original_url
    print("✅ Patched DATABASE_URL using proxy.rlwy.net override for staging.", flush=True)
else:
    print("ℹ️ Using DATABASE_URL as-is", flush=True)

print("📦 DATABASE_URL at runtime (from app.py):", os.getenv("DATABASE_URL"), flush=True)
print(f"[Startup] STRAVA_REDIRECT_URI raw from environment: '{os.getenv('STRAVA_REDIRECT_URI')}'", flush=True)
print(f"✅ Loaded environment: {env_path}", flush=True)
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

# ✅ Serve from absolute build path
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist"))


def create_app(test_config=None):
    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="/")
    cors_origins = os.getenv("CORS_ORIGINS", "")
    origin_list = [o.strip() for o in cors_origins.split(",") if o.strip()]
    CORS(app, supports_credentials=True, origins=origin_list)

    # 🔐 App config
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

    # ✅ Debug route to list files in /dist
    @app.route("/debug-files")
    def debug_files():
        try:
            files = []
            for root, dirs, filenames in os.walk(app.static_folder):
                for f in filenames:
                    rel_path = os.path.relpath(os.path.join(root, f), app.static_folder)
                    files.append(rel_path)
            return {
                "static_folder": app.static_folder,
                "files": files
            }
        except Exception as e:
            return {"error": str(e)}, 500

    # 🧪 Other debug utilities
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
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
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

    # 🔁 Post OAuth redirect
    @app.route("/post-oauth")
    def post_oauth():
        if raw_env_mode == "local":
            return redirect(os.getenv("FRONTEND_REDIRECT"))
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        return "❌ Frontend not found", 404

    # 🧭 Universal frontend handler (fallback)
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        print("📁 Serving from:", app.static_folder)
        full_path = os.path.join(app.static_folder, path)
        print(f"🔍 Request for: {path} → Resolved path: {full_path}")
        if path and os.path.exists(full_path) and not path.endswith("/"):
            return send_from_directory(app.static_folder, path)
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        return "❌ Frontend index.html not found", 404

    return app

# 🔄 Entry point
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
