from flask import (
    Blueprint,
    redirect,
    request,
    jsonify,
    session as flask_session,
    current_app,
)
import traceback
import requests
from datetime import datetime, timedelta
import jwt
import os

from src.db.dao.activity_dao import has_existing_activities
from src.db.db_session import get_session
import src.utils.config as config

from src.services.token_service import (
    refresh_token_if_expired,
    delete_athlete_tokens,
    store_tokens_from_callback,
)
from src.db.dao.athlete_dao import upsert_athlete
from src.services.ingestion_orchestrator_service import (
    run_full_ingestion_and_enrichment,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/whoami", methods=["GET"])
def whoami():
    athlete_id = flask_session.get("athlete_id")
    print(f"📩 /whoami called. Session contents: {dict(flask_session)}", flush=True)

    if not athlete_id:
        return jsonify({"error": "Not logged in"}), 401

    session = get_session()
    try:
        synced = has_existing_activities(session, athlete_id)
        return jsonify({"athlete_id": athlete_id, "already_synced": synced}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@auth_bp.route("/login", methods=["POST"])
def admin_login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if username == config.ADMIN_USER and password == config.ADMIN_PASS:
            access_token = jwt.encode(
                {
                    "sub": username,
                    "exp": datetime.utcnow()
                    + timedelta(seconds=config.ACCESS_TOKEN_EXP),
                },
                config.SECRET_KEY,
                algorithm="HS256",
            )
            refresh_token = jwt.encode(
                {
                    "sub": username,
                    "exp": datetime.utcnow()
                    + timedelta(seconds=config.REFRESH_TOKEN_EXP),
                },
                config.SECRET_KEY,
                algorithm="HS256",
            )
            return (
                jsonify({"access_token": access_token, "refresh_token": refresh_token}),
                200,
            )
        else:
            return jsonify({"error": "Unauthorized"}), 401
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/login", methods=["GET"])
def strava_login():
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "").strip().rstrip(";")
    client_id = os.getenv("STRAVA_CLIENT_ID")

    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return redirect(url)


from urllib.parse import urlencode


@auth_bp.route("/callback", methods=["GET"])
def callback():
    session = get_session()
    try:
        code = request.args.get("code")
        if not code:
            return "❌ Missing OAuth code", 400

        redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "").strip().rstrip(";")
        frontend_redirect = os.getenv("FRONTEND_REDIRECT", "").strip().rstrip(";")

        if not frontend_redirect:
            raise ValueError("Missing FRONTEND_REDIRECT in environment.")

        print(
            f"[Callback] Redirect URI used for token exchange: {redirect_uri}",
            flush=True,
        )

        athlete_id = store_tokens_from_callback(code, session, redirect_uri)
        flask_session["athlete_id"] = athlete_id

        print(
            f"✅ Flask session contents before redirect: {dict(flask_session)}",
            flush=True,
        )

        query = urlencode({"code": code, "authed": "true"})
        full_redirect_url = f"{frontend_redirect}?{query}"
        print(f"[Callback] REDIRECT FINAL URL: {full_redirect_url}", flush=True)

        return redirect(full_redirect_url)

    except Exception as e:
        traceback.print_exc()
        return "❌ Internal Server Error", 500

    finally:
        session.close()


@auth_bp.route("/callback", methods=["POST"])
def callback_token_exchange():
    session = get_session()
    try:
        data = request.get_json()
        code = data.get("code")

        if not code:
            return jsonify({"error": "Missing OAuth code"}), 400

        redirect_uri = os.getenv("STRAVA_REDIRECT_URI", "").strip().rstrip(";")
        athlete_id = store_tokens_from_callback(code, session, redirect_uri)

        flask_session["athlete_id"] = athlete_id
        return jsonify({"status": "success", "athlete_id": athlete_id}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


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
        data = request.get_json()
        athlete_id = data.get("athlete_id")
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()

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
