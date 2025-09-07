from flask import (
    Blueprint,
    redirect,
    request,
    jsonify,
    session as flask_session,
    current_app,
)
import traceback
import os
from urllib.parse import urlencode
import requests  # for HTTPError type

from src.db.dao.activity_dao import has_existing_activities
from src.db.db_session import get_session
import src.utils.config as config
from src.db.models.athletes import Athlete
from src.db.dao import user_athletes_dao

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

# ✅ Use our single source of truth for JWT
from src.utils.auth0_jwt import verify_and_decode

from sqlalchemy import text

auth_bp = Blueprint("auth", __name__)


# ------------------------------------------------------------
# Who am I? (reads Flask session set by /auth/callback)
# ------------------------------------------------------------

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]


# ------------------------------------------------------------
# Legacy /auth/login (GET) → keep as a harmless Strava redirect shim
# ------------------------------------------------------------
@auth_bp.route("/login", methods=["GET"])
def login_redirect_alias():
    return strava_login_redirect()


# ------------------------------------------------------------
# Strava OAuth start (+ alias)
# ------------------------------------------------------------
from src.utils.auth0_jwt import verify_and_decode


@auth_bp.route("/strava-login", methods=["GET"])
def strava_login_redirect():
    print("🛑 Flask route /auth/strava-login was triggered", flush=True)

    redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")
    client_id = os.getenv("STRAVA_CLIENT_ID") or ""

    # ✅ Extract user_id from JWT cookie or fallback to query param
    jwt = request.cookies.get("user_jwt")
    user_id = request.args.get("user_id")  # ← Add this fallback

    if jwt:
        try:
            payload = verify_and_decode(jwt)
            user_id = (
                payload.get("sub") or user_id
            )  # ← Safely prefer cookie, fallback to query
        except Exception as e:
            print(f"⚠️ Failed to decode JWT: {e}", flush=True)

    # 🏁 Build the redirect URL with optional `state=user_id`
    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    if user_id:
        url += f"&state={user_id}"

    print(f"🔗 Redirecting to Strava URL: {url}", flush=True)
    return redirect(url)


@auth_bp.route("/strava/connect", methods=["GET"])
def strava_connect_alias():
    return strava_login_redirect()


@auth_bp.route("/debug/set", methods=["GET"])
def debug_set_cookie():
    flask_session["athlete_id"] = "debug-athlete"
    flask_session.permanent = True
    return jsonify({"status": "set", "session": dict(flask_session)}), 200


@auth_bp.route("/debug/show", methods=["GET"])
def debug_show_cookie():
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
        frontend_base = (
            (os.getenv("FRONTEND_BASE_URL") or "http://localhost:5173")
            .strip()
            .rstrip("/")
        )

        if not client_id or not client_secret or not redirect_uri:
            return (
                jsonify({"error": "Callback error", "detail": "Missing Strava env"}),
                502,
            )

        print(
            f"[Callback] Redirect URI used for token exchange: {redirect_uri}",
            flush=True,
        )

        # 🔑 Step 1: Store Strava tokens and get athlete_id
        try:
            athlete_id = token_service.store_tokens_from_callback(
                code, session, redirect_uri
            )
            upsert_athlete(
                session,
                athlete_id,
                strava_athlete_id=athlete_id,
            )
        except requests.exceptions.HTTPError as e:
            return jsonify({"error": "Callback error", "detail": str(e)}), 502

        flask_session["athlete_id"] = athlete_id
        print(f"✅ Stored tokens. Athlete ID: {athlete_id}", flush=True)

        # ✅ Step 2: Link user_id → athlete_id from `state` param
        user_id = request.args.get("state")
        if user_id:
            try:
                athlete_row = (
                    session.query(Athlete)
                    .filter_by(strava_athlete_id=athlete_id)
                    .first()
                )
                if not athlete_row:
                    raise Exception(
                        f"Athlete with strava_athlete_id={athlete_id} not found in DB"
                    )

                internal_athlete_id = athlete_row.id

                # ✅ Use clean DAO method
                user_athletes_dao.create_link(
                    user_id=user_id, athlete_id=internal_athlete_id
                )
                print(
                    f"✅ Linked user {user_id} to athlete {internal_athlete_id}",
                    flush=True,
                )

            except Exception as e:
                print(f"❌ Failed to insert into user_athletes: {e}", flush=True)

        # ✅ Final redirect
        if current_app.testing:
            return f"Token stored and user linked to athlete_id: {athlete_id}", 200

        return redirect(f"{frontend_base}/dashboard?strava=success")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "Callback error", "detail": str(e)}), 500
    finally:
        session.close()


# ------------------------------------------------------------
# Strava OAuth callback (POST JSON exchange)
# ------------------------------------------------------------
@auth_bp.route("/callback", methods=["POST"])
def callback_token_exchange():
    session = get_session()
    try:
        data = request.get_json() or {}
        code = data.get("code")
        user_id = data.get("user_id")  # Frontend must include this in the POST

        if not code or not user_id:
            return jsonify({"error": "Missing OAuth code or user_id"}), 400

        redirect_uri = (os.getenv("STRAVA_REDIRECT_URI") or "").strip().rstrip(";")

        # 1. Exchange token with Strava
        token_data = token_service.exchange_token(code, redirect_uri)
        strava_athlete_id = token_data["athlete"]["id"]

        # 2. Store the token
        token_service.store_strava_token(
            session, user_id, strava_athlete_id, token_data
        )

        # 3. Get or insert internal athlete ID
        athlete_id = token_service.get_athlete_id_from_strava_id(
            session, strava_athlete_id
        )
        if athlete_id is None:
            athlete_id = token_service.insert_athlete(session, strava_athlete_id)

        # 4. Insert or update user_athletes
        stmt = text(
            """
            INSERT INTO user_athletes (user_id, athlete_id)
            VALUES (:uid, :aid)
            ON CONFLICT (user_id) DO UPDATE SET athlete_id = EXCLUDED.athlete_id
        """
        )
        session.execute(stmt, {"uid": user_id, "aid": athlete_id})
        session.commit()

        return jsonify({"status": "success", "athlete_id": athlete_id}), 200

    except Exception as e:
        session.rollback()
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
            # ✅ Use Auth0 RS256 verify instead of HS256
            verify_and_decode(token)
        except Exception as e:
            return jsonify({"error": f"Invalid token: {str(e)}"}), 401

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
# Diagnostics / profile / ingest
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
