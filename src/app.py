# app.py

import os
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse
from flask_session import Session
from werkzeug.exceptions import HTTPException
import uuid

# Environment Setup
# Only load .env.local if it exists (for local development)
# On Railway/production, environment variables are set directly - no files needed
env_local_path = Path(".env.local")
if env_local_path.exists():
    load_dotenv(env_local_path, override=False)  # Don't override what run.py loaded
    print(f"[OK] Using local environment file: .env.local", flush=True)
else:
    # On Railway/production, environment variables are already set
    print("[OK] Using system environment variables (Railway/production)", flush=True)

# Patch for Railway proxy handling
original_url = os.getenv("DATABASE_URL", "")
parsed = urlparse(original_url)
if parsed.hostname and "proxy.rlwy.net" in parsed.hostname:
    os.environ["DATABASE_URL"] = original_url
    print(
        "[OK] Patched DATABASE_URL using proxy.rlwy.net override for staging.",
        flush=True,
    )
else:
    print("[INFO] Using DATABASE_URL as-is", flush=True)

from src.utils.security_utils import redact_connection_string

print(
    "[INFO] DATABASE_URL at runtime (from app.py):",
    redact_connection_string(os.getenv("DATABASE_URL")),
    flush=True,
)
print(
    f"[Startup] STRAVA_REDIRECT_URI raw from environment: '{os.getenv('STRAVA_REDIRECT_URI')}'",
    flush=True,
)
print(f"[INFO] STRAVA_REDIRECT_URI = {os.getenv('STRAVA_REDIRECT_URI')}", flush=True)

# Debug Auth0 vars
print(f"[INFO] AUTH0_DOMAIN={os.getenv('AUTH0_DOMAIN')}", flush=True)
print(f"[INFO] AUTH0_AUDIENCE={os.getenv('AUTH0_AUDIENCE')}", flush=True)
print(f"[INFO] AUTH0_ISSUER={os.getenv('AUTH0_ISSUER')}", flush=True)
print(f"[INFO] AUTH0_ALGORITHMS={os.getenv('AUTH0_ALGORITHMS')}", flush=True)

# Flask Setup
from flask import Flask, request, jsonify, g, session
from flask_cors import CORS
from src.utils.config import config
from src.routes.admin_routes import admin_bp
from src.routes.auth_routes import auth_bp
from src.routes.activity_routes import activity_bp
from src.routes.health_routes import health_bp

# Removed ask_routes - using conversation system instead
from src.routes.user_profile_routes import user_profile_bp
from src.routes.user_identity_routes import identity_bp
from src.routes.auth_me_routes import auth_me_bp
from src.routes.user_data_routes import user_data_bp
from src.routes.strava_connection_routes import strava_connection_bp
from src.utils.auth0_jwt import requires_auth
from src.routes.metrics_routes import metrics_bp
from src.routes.webhook_routes import webhook_bp
from src.routes.longest_runs_routes import longest_runs_bp
from src.routes.gyr_metrics_routes import gyr_metrics_bp
from src.routes.plan_routes import plan_bp
from src.routes.conversation_routes import conversation_bp


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_ECHO"] = False

    from src.db.db_session import db

    # CORS setup
    cors_origins = os.getenv("CORS_ORIGINS", "https://app.smartcoach.dev")
    origin_list = [o.strip().strip(";") for o in cors_origins.split(",") if o.strip()]
    CORS(
        app,
        origins=origin_list,
        supports_credentials=True,
        allow_headers=["Authorization", "Content-Type", "X-User-Id"],
        expose_headers=["Content-Type", "Authorization"],
    )
    print("[DEBUG] Raw CORS_ORIGINS from env:", repr(cors_origins), flush=True)
    print("[DEBUG] Allowed CORS origins:", origin_list, flush=True)

    # Cookie/session handling
    app.config.update(
        SESSION_COOKIE_NAME="smartcoach_session",
        SESSION_COOKIE_SAMESITE="None",
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_PATH="/",
        SESSION_COOKIE_DOMAIN=os.getenv("SESSION_COOKIE_DOMAIN"),
    )

    # Required app config values
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),
        SESSION_TYPE="filesystem",
    )

    db.init_app(app)

    import src.db.models

    Session(app)

    if test_config:
        app.config.update(test_config)

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(identity_bp, url_prefix="")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(activity_bp, url_prefix="/api/activities")
    app.register_blueprint(health_bp)
    # Removed ask_bp - using conversation system instead
    app.register_blueprint(user_profile_bp)
    app.register_blueprint(user_data_bp, url_prefix="/api")
    app.register_blueprint(strava_connection_bp)
    app.register_blueprint(metrics_bp, url_prefix="/api/metrics")
    app.register_blueprint(longest_runs_bp, url_prefix="/api/longest-runs")
    app.register_blueprint(gyr_metrics_bp, url_prefix="/api/gyr-metrics")
    app.register_blueprint(plan_bp)
    app.register_blueprint(auth_me_bp)
    app.register_blueprint(webhook_bp, url_prefix="/webhooks")
    app.register_blueprint(conversation_bp, url_prefix="/api")

    # Log all registered routes for debugging
    print("[BLUEPRINT_REGISTRATION] All blueprints registered", flush=True)
    print(f"[BLUEPRINT_REGISTRATION] Admin blueprint name: {admin_bp.name}", flush=True)
    print(
        f"[BLUEPRINT_REGISTRATION] Admin blueprint registered with prefix: /admin",
        flush=True,
    )
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("admin."):
            print(
                f"[BLUEPRINT_REGISTRATION] Admin route: {rule.endpoint} -> {rule.rule}",
                flush=True,
            )

    @app.route("/_debug/db-url")
    def debug_db_url():
        from src.db.db_session import engine

        return {"connected_url": str(engine.url)}, 200

    @app.route("/debug/session/set")
    def set_session_for_debug():
        session["debug"] = "value"
        return "[OK] Session set", 200

    # Global OPTIONS handler for preflight support
    @app.before_request
    def log_request_details():
        origin = request.headers.get("Origin")
        method = request.method
        path = request.path
        user_agent = request.headers.get("User-Agent", "unknown")
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        print("[DEBUG] Request Metadata:", flush=True)
        print(f"  - ID: {request_id}", flush=True)
        print(f"  - Method: {method}", flush=True)
        print(f"  - Path: {path}", flush=True)
        print(f"  - Origin: {origin}", flush=True)
        print(f"  - User-Agent: {user_agent}", flush=True)
        print("[DEBUG] Request cookies:", request.cookies, flush=True)

        # Special logging for conversations endpoint
        if path.startswith("/api/conversations"):
            print(f"[CONVERSATIONS] Request received: {method} {path}", flush=True)
            auth_header = request.headers.get("Authorization", "")
            print(
                f"[CONVERSATIONS] Authorization header present: {bool(auth_header)}, length: {len(auth_header)}",
                flush=True,
            )

        # Log ALL requests to see what's happening
        if path.startswith("/api/"):
            print(f"[API_REQUEST] {method} {path}", flush=True)

        # Log ALL requests to see what's happening
        print(f"[ALL_REQUESTS] {method} {path}", flush=True)

        # Log auth header for debug
        if "Authorization" in request.headers:
            print(
                "[DEBUG] Authorization header present (len={}):".format(
                    len(request.headers["Authorization"])
                ),
                flush=True,
            )

        if method == "OPTIONS":
            print("[DEBUG] Handling OPTIONS preflight", flush=True)
            resp = app.make_response("")
            resp.status_code = 204
            # Add CORS headers here
            resp.headers["Access-Control-Allow-Origin"] = (
                origin or "https://app.smartcoach.dev"
            )
            resp.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-User-Id"
            )
            resp.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            return resp

    # CORS + Cookie debugging
    @app.after_request
    def apply_cors_and_debug(response):
        request_origin = request.headers.get("Origin")
        allowed_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",")]

        if request_origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = request_origin
            response.headers["Access-Control-Allow-Credentials"] = "true"

        print(
            "[DEBUG] Set-Cookie header:", response.headers.get("Set-Cookie"), flush=True
        )
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

    @app.route("/hello", methods=["POST"])
    def hello():
        print("hello route called")
        return jsonify({"hello": "ok"})

    return app


# Entry point
app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
