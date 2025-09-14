import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse
from flask_session import Session
from werkzeug.exceptions import HTTPException


# 📦 Environment Setup
raw_env_mode = os.environ.get("FLASK_ENV", "production")
env_path = {
    "local": ".env.local",
    "staging": ".env.staging",
    "production": ".env.prod",
}.get(raw_env_mode, ".env")

load_dotenv(env_path, override=True)
print(f"🔍 Loaded environment file: {env_path}", flush=True)

# ⛏️ Patch for Railway proxy handling
original_url = os.getenv("DATABASE_URL", "")
parsed = urlparse(original_url)
if parsed.hostname and "proxy.rlwy.net" in parsed.hostname:
    os.environ["DATABASE_URL"] = original_url
    print(
        "✅ Patched DATABASE_URL using proxy.rlwy.net override for staging.", flush=True
    )
else:
    print("ℹ️ Using DATABASE_URL as-is", flush=True)

print(
    "📦 DATABASE_URL at runtime (from app.py):", os.getenv("DATABASE_URL"), flush=True
)
print(
    f"[Startup] STRAVA_REDIRECT_URI raw from environment: '{os.getenv('STRAVA_REDIRECT_URI')}'",
    flush=True,
)
print(f"✅ Loaded environment: {env_path}", flush=True)
print(f"📍 STRAVA_REDIRECT_URI = {os.getenv('STRAVA_REDIRECT_URI')}", flush=True)


# 🔑 Debug Auth0 vars
print(f"🔑 AUTH0_DOMAIN={os.getenv('AUTH0_DOMAIN')}", flush=True)
print(f"🔑 AUTH0_AUDIENCE={os.getenv('AUTH0_AUDIENCE')}", flush=True)
print(f"🔑 AUTH0_ISSUER={os.getenv('AUTH0_ISSUER')}", flush=True)
print(f"🔑 AUTH0_ALGORITHMS={os.getenv('AUTH0_ALGORITHMS')}", flush=True)


# 🌐 Flask Setup
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from src.utils.config import config
from src.routes.admin_routes import admin_bp
from src.routes.auth_routes import auth_bp
from src.routes.activity_routes import activity_bp
from src.routes.health_routes import health_bp
from src.routes.ask_routes import ask_bp
from src.routes.user_profile_routes import user_profile_bp
from src.routes.user_identity_routes import identity_bp
from src.routes.auth_me_routes import auth_me_bp
from src.utils.auth0_jwt import requires_auth
from src.routes.plan_routes import plan_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_ECHO"] = False

    from src.db.db_session import db

    # ✅ CORS setup
    cors_origins = os.getenv("CORS_ORIGINS", "https://app.smartcoach.dev")
    origin_list = [o.strip().strip(";") for o in cors_origins.split(",") if o.strip()]
    CORS(
        app,
        origins=origin_list,
        supports_credentials=True,
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Type", "Authorization"],
    )
    print("🔬 Raw CORS_ORIGINS from env:", repr(cors_origins), flush=True)
    print("🛂 Allowed CORS origins:", origin_list, flush=True)

    # 🔐 Cookie/session handling
    app.config.update(
        SESSION_COOKIE_NAME="smartcoach_session",
        SESSION_COOKIE_SAMESITE="None",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_DOMAIN=".smartcoach.dev",
        SESSION_COOKIE_PATH="/",
    )

    # ✅ Required app config values
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),
        CRON_SECRET_KEY=config.CRON_SECRET_KEY,
        INTERNAL_API_KEY=config.INTERNAL_API_KEY,
        SESSION_TYPE="filesystem",
    )

    db.init_app(app)

    import src.db.models

    Session(app)

    if test_config:
        app.config.update(test_config)

    # 🔗 Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(activity_bp, url_prefix="/api/activities")
    app.register_blueprint(health_bp)
    app.register_blueprint(ask_bp)
    app.register_blueprint(user_profile_bp)
    app.register_blueprint(identity_bp)
    app.register_blueprint(auth_me_bp)
    app.register_blueprint(plan_bp)

    @app.route("/_debug/db-url")
    def debug_db_url():
        from src.db.db_session import engine

        return {"connected_url": str(engine.url)}, 200

    # ✅ Global OPTIONS handler for preflight support
    @app.before_request
    def log_request_details():
        origin = request.headers.get("Origin")
        method = request.method
        print(f"🌐 Incoming request from Origin: {origin}", flush=True)
        print(f"📡 Incoming {method} request to: {request.path}", flush=True)
        print("🍪 Request cookies:", request.cookies, flush=True)

        # Log auth header for debug
        if "Authorization" in request.headers:
            print(
                "🔐 Authorization header present (len={}):".format(
                    len(request.headers["Authorization"])
                ),
                flush=True,
            )

        if method == "OPTIONS":
            print("🚦 Handling OPTIONS preflight", flush=True)
            return ("", 204)

    @app.after_request
    def debug_cookie(response):
        print("🔍 Set-Cookie header:", response.headers.get("Set-Cookie"), flush=True)
        return response

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
                "split_column": (
                    {
                        "name": split_col["name"],
                        "type": str(split_col["type"]),
                        "nullable": split_col["nullable"],
                    }
                    if split_col
                    else "not found"
                ),
            }
        except Exception as e:
            import traceback

            traceback.print_exc()
            return {"status": "fail", "error": str(e)}, 500

    if os.getenv("DEBUG_AUTH") == "1":

        @app.get("/_debug/headers")
        def _debug_headers():
            auth = request.headers.get("Authorization", "")
            prefix = auth[:20]
            return (
                jsonify(
                    {
                        "has_authorization": bool(auth),
                        "authorization_prefix": prefix,
                        "authorization_len": len(auth),
                        "origin": request.headers.get("Origin"),
                        "path": request.path,
                    }
                ),
                200,
            )

        @app.get("/_debug/me")
        @requires_auth
        def _debug_me():
            return (
                jsonify(
                    {
                        "ok": True,
                        "claims": getattr(g, "current_user", {}),
                    }
                ),
                200,
            )

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            response = e.get_response()
            return (
                jsonify({"error": e.name, "message": e.description, "code": e.code}),
                e.code,
            )
        return (
            jsonify({"error": "Internal Server Error", "message": str(e), "code": 500}),
            500,
        )

    return app


# 🔄 Entry point
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
