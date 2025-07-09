import os
from dotenv import load_dotenv

# At the top of app.py
# trigger: redeploy

# 🌍 Load correct .env file
raw_env_mode = os.environ.get("FLASK_ENV", "production")
env_path = {
    "test": ".env.test",
    "production": ".env.prod"
}.get(raw_env_mode, ".env")

load_dotenv(env_path, override=True)
print(f"✅ Loaded environment: {env_path}", flush=True)

if env_path != ".env":
    print("🚫 Skipping .env fallback", flush=True)
else:
    print("ℹ️ Default .env used", flush=True)

print(f"📍 STRAVA_REDIRECT_URI = {os.getenv('STRAVA_REDIRECT_URI')}", flush=True)

# 🚀 Flask Setup
from flask import Flask, send_from_directory, redirect
import src.utils.config as config
from src.routes.admin_routes import admin_bp
from src.routes.auth_routes import auth_bp
from src.routes.activity_routes import activity_bp
from src.routes.health_routes import health_bp
from src.routes.ask_routes import ask_bp
from pathlib import Path
from flask_cors import CORS


def create_app(test_config=None):
    print("✅ ENTERED create_app()", flush=True)
    print("📁 CWD:", os.getcwd(), flush=True)
    print("📁 Contents of current working dir:", os.listdir(os.getcwd()), flush=True)
    print("📁 static/ contents:", os.listdir("static"), flush=True)

    print("DEBUG ENV VARS:")
    print(f"DATABASE_URL={os.getenv('DATABASE_URL')}", flush=True)
    print(f"STRAVA_REDIRECT_URI={os.getenv('STRAVA_REDIRECT_URI')}", flush=True)

    # ✅ Use universal static folder location
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parent.parent
    #app = Flask(__name__, static_folder=str(BASE_DIR / "static"), static_url_path="/")
    #app = Flask(__name__, static_folder="static", static_url_path="/")
    
    app = Flask(__name__, static_folder="../static", static_url_path="/")
    CORS(app, supports_credentials=True)




    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_URL=os.getenv("DATABASE_URL"),
        CRON_SECRET_KEY=config.CRON_SECRET_KEY,
        INTERNAL_API_KEY=config.INTERNAL_API_KEY,
        SESSION_TYPE="filesystem"
    )

    if test_config:
        app.config.update(test_config)

    # 🔗 Register Blueprints
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

    # ✅ SPA-compatible route for post-OAuth redirect
    @app.route("/post-oauth")
    def post_oauth():
        env = os.getenv("FLASK_ENV", "production")
        print(f"🧪 /post-oauth triggered (FLASK_ENV={env})", flush=True)

        # ✅ Local dev: redirect to Vite server
        if env in ["development", "test"]:
            print("🔄 Redirecting to localhost Vite dev server", flush=True)
            redirect_url = os.getenv("FRONTEND_REDIRECT")
            print(f"🔄 Redirecting to: {redirect_url}", flush=True)
            return redirect(redirect_url)

        # ✅ Production: Serve index.html
        index_path = os.path.join(app.static_folder, "index.html")
        print(f"🧾 Looking for index.html at: {index_path}", flush=True)

        exists = os.path.exists(index_path)
        print(f"📁 Does index.html exist? {exists}", flush=True)

        if exists:
            print("📦 Serving index.html", flush=True)
            return send_from_directory(app.static_folder, "index.html")

        print("❌ index.html not found - returning 404", flush=True)
        return "❌ Frontend not found", 404


    # Root route (optional)
    #@app.route("/")
    #def home():
    #    return "✅ OAuth complete. You are now logged in!", 200

    # 🧾 Catch-all for unmatched routes — needed for React Router in production
    @app.errorhandler(404)
    def spa_fallback(e):
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        return "404 Not Found", 404

    print("✅ Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}", flush=True)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000)
