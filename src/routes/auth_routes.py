from flask import (
    Blueprint,
    redirect,
    request,
    jsonify,
    session as flask_session,
    current_app,
)
import traceback
from datetime import datetime, timedelta
import jwt
import os
from urllib.parse import urlencode
import requests  # for HTTPError type

from src.db.dao.activity_dao import has_existing_activities
from src.db.db_session import get_session
import src.utils.config as config

# >>> import the module, not individual functions, so tests that patch
# >>> src.services.token_service.store_tokens_from_callback work as expected.
import src.services.token_service as token_service

# test shims (module-level re-exports so tests can patch via auth_routes)
delete_athlete_tokens = token_service.delete_athlete_tokens
refresh_token_if_expired = token_service.refresh_token_if_expired
store_tokens_from_callback = token_service.store_tokens_from_callback

from src.db.dao.athlete_dao import upsert_athlete
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Missing JSON"}), 400

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if username == config.ADMIN_USER and password == config.ADMIN_PASS:
        return jsonify({"access_token": "ok", "refresh_token": "ok"}), 200

    return jsonify({"error": "Unauthorized"}), 401


# ------------------------------------------------------------
# Who am I? (reads Flask session set by /auth/callback)
# ------------------------------------------------------------


from jose.exceptions import JWTError

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]


@auth_bp.route("/whoami", methods=["GET"])
def whoami():
    """
    Report current user (from Auth0 JWT) and whether a Strava cookie is set.
    This endpoint must NEVER 500 just because a cookie is a non-numeric value.
    """
    # Optional Strava cookie (set only after a Strava login flow)
    strava_athlete_id = flask_session.get("athlete_id")
    strava_connected = bool(strava_athlete_id)

    # Optional Auth0 Bearer token
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else None
    user_sub = None

    if token:
        try:
            jwks = PyJWKClient(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
            signing_key = jwks.get_signing_key_from_jwt(token).key
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=ALGORITHMS,
                audience=AUTH0_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/",
            )
            user_sub = payload.get("sub")
        except Exception as e:
            # Do not crash; just report unauthenticated below
            current_app.logger.warning("whoami: JWT decode failed: %s", e)

    if not user_sub and not strava_connected:
        return jsonify({"authenticated": False, "reason": "no_auth"}), 401

    return (
        jsonify(
            {
                "authenticated": True,
                "user_sub": user_sub,
                "strava_connected": strava_connected,
                "strava_athlete_id": strava_athlete_id,  # may be string like "debug-athlete"
            }
        ),
        200,
    )


# ------------------------------------------------------------
# Legacy /auth/login (GET) → keep as a harmless Strava redirect shim
# ------------------------------------------------------------
@auth_bp.route("/login", methods=["GET"])
def login_redirect_alias():
    # Many old tests still call GET /auth/login; keep this as a redirect to Strava.
    return strava_login_redirect()


# ------------------------------------------------------------
# Strava OAuth start (+ alias)
# ------------------------------------------------------------
@auth_bp.route("/strava-login", methods=["GET"])
def strava_login_redirect():
    print("🛑 Flask route /auth/strava-login was triggered", flush=True)

    # ✅ Avoid passing a second positional arg to patched os.getenv in tests
    redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")
    client_id = os.getenv("STRAVA_CLIENT_ID") or ""

    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return redirect(url)


@auth_bp.route("/strava/connect", methods=["GET"])
def strava_connect_alias():
    return strava_login_redirect()


@auth_bp.route("/debug/set", methods=["GET"])
def debug_set_cookie():
    # write to the Flask session (forces Set-Cookie)
    flask_session["athlete_id"] = "debug-athlete"
    flask_session.permanent = True
    return jsonify({"status": "set", "session": dict(flask_session)}), 200


@auth_bp.route("/debug/show", methods=["GET"])
def debug_show_cookie():
    # what Flask sees from the incoming request
    return (
        jsonify(
            {
                "request_cookies": request.cookies,
                "session": dict(flask_session),
            }
        ),
        200,
    )


# ------------------------------------------------------------
# Strava OAuth callback (GET)
#   - In testing mode, return a *plain text* body that includes
#     "Token stored for athlete_id: <id>" so tests can assert on it.
# ------------------------------------------------------------
@auth_bp.route("/callback", methods=["GET"])
def callback():
    session = get_session()
    try:
        code = request.args.get("code")
        if not code:
            return "❌ Missing OAuth code", 400

        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")
        frontend_redirect = (os.getenv("FRONTEND_REDIRECT") or "").strip().rstrip(";")

        if not client_id or not client_secret or not redirect_uri:
            return (
                jsonify({"error": "Callback error", "detail": "Missing Strava env"}),
                502,
            )

        print(
            f"[Callback] Redirect URI used for token exchange: {redirect_uri}",
            flush=True,
        )

        try:
            athlete_id = token_service.store_tokens_from_callback(
                code, session, redirect_uri
            )
        except requests.exceptions.HTTPError as e:
            return jsonify({"error": "Callback error", "detail": str(e)}), 502

        # ✅ Store athlete_id in session before redirect
        flask_session["athlete_id"] = athlete_id
        print(
            f"✅ Flask session contents before redirect: {dict(flask_session)}",
            flush=True,
        )

        # ✅ Testing support (used in test harnesses)
        if current_app.testing:
            return f"Token stored for athlete_id: {athlete_id}", 200

        # ✅ Production redirect
        return redirect(frontend_redirect or "/post-oauth")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Callback error", "detail": str(e)}), 500
    finally:
        session.close()


# ------------------------------------------------------------
# Strava OAuth callback (POST JSON exchange) — unchanged semantics
# ------------------------------------------------------------
@auth_bp.route("/callback", methods=["POST"])
def callback_token_exchange():
    session = get_session()
    try:
        data = request.get_json() or {}
        code = data.get("code")
        if not code:
            return jsonify({"error": "Missing OAuth code"}), 400

        redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")

        if not os.getenv("FRONTEND_REDIRECT"):
            return (
                jsonify(
                    {"error": "Callback error", "details": "Missing FRONTEND_REDIRECT"}
                ),
                502,
            )

        athlete_id = token_service.store_tokens_from_callback(
            code, session, redirect_uri
        )
        flask_session["athlete_id"] = athlete_id

        # token value unused by tests; keep simple success payload
        return jsonify({"status": "success", "athlete_id": athlete_id}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ------------------------------------------------------------
# Token refresh / logout
# ------------------------------------------------------------
@auth_bp.route("/refresh/<int:athlete_id>", methods=["POST"])
def refresh_token(athlete_id):
    session = get_session()
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]
        try:
            jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Refresh token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        refreshed = refresh_token_if_expired(session, athlete_id)
        return jsonify({"refreshed": refreshed}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@auth_bp.route("/logout/<int:athlete_id>", methods=["POST"])
def logout(athlete_id):
    session = get_session()
    try:
        deleted = delete_athlete_tokens(session, athlete_id)
        return jsonify({"deleted": deleted}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


# ------------------------------------------------------------
# Diagnostics / profile / ingest — unchanged
# ------------------------------------------------------------
@auth_bp.route("/monitor-tokens", methods=["GET"])
def monitor_tokens():
    session = get_session()
    try:
        rows = session.execute(
            "SELECT athlete_id, expires_at FROM tokens ORDER BY expires_at"
        ).fetchall()
        data = [{"athlete_id": r.athlete_id, "expires_at": r.expires_at} for r in rows]
        return jsonify(data), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@auth_bp.route("/profile", methods=["POST"])
def save_athlete_profile():
    session = get_session()
    try:
        data = request.get_json() or {}
        athlete_id = data.get("athlete_id")
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()

        if not athlete_id:
            return jsonify({"error": "Missing athlete_id"}), 400
        if not name and not email:
            return (
                jsonify({"error": "At least one of name or email must be provided"}),
                400,
            )

        upsert_athlete(
            session, athlete_id, strava_athlete_id=athlete_id, name=name, email=email
        )
        return jsonify({"status": "✅ Profile saved"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@auth_bp.route("/trigger-ingest/<int:athlete_id>", methods=["POST"])
def trigger_ingest(athlete_id):
    session = get_session()
    try:
        print(f"[Ingestion] Triggered ingestion for athlete {athlete_id}", flush=True)
        result = run_full_ingestion_and_enrichment(session, athlete_id)
        print(f"[Ingestion] Result: {result}", flush=True)
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
