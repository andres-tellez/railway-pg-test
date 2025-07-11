from flask import Blueprint, redirect, request, jsonify, session as flask_session, current_app
import traceback
import requests
from datetime import datetime, timedelta
import jwt
import os

import src.utils.config as config
from src.services.token_service import (
    refresh_token_if_expired,
    delete_athlete_tokens
)
from src.db.db_session import get_session

auth_bp = Blueprint("auth", __name__)

@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    athlete_id = flask_session.get("athlete_id")
    if not athlete_id:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"athlete_id": athlete_id})

@auth_bp.route("/login", methods=["POST"])
def admin_login():
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if username == config.ADMIN_USER and password == config.ADMIN_PASS:
            access_token = jwt.encode(
                {"sub": username, "exp": datetime.utcnow() + timedelta(seconds=config.ACCESS_TOKEN_EXP)},
                config.SECRET_KEY, algorithm="HS256"
            )
            refresh_token = jwt.encode(
                {"sub": username, "exp": datetime.utcnow() + timedelta(seconds=config.REFRESH_TOKEN_EXP)},
                config.SECRET_KEY, algorithm="HS256"
            )
            return jsonify({
                "access_token": access_token,
                "refresh_token": refresh_token
            }), 200
        else:
            return jsonify({"error": "Unauthorized"}), 401
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@auth_bp.route("/login", methods=["GET"])
def strava_login():
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI")
    client_id = os.getenv("STRAVA_CLIENT_ID")

    print(f"🌐 OAuth Login Triggered", flush=True)
    print(f"🔑 STRAVA_CLIENT_ID = {client_id}", flush=True)
    print(f"📍 STRAVA_REDIRECT_URI = {redirect_uri}", flush=True)

    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return redirect(url)

@auth_bp.route("/callback")
def callback():
    from src.services.token_service import store_tokens_from_callback
    session = get_session()
    try:
        code = request.args.get("code")
        if not code:
            print("❌ Missing code param", flush=True)
            return "❌ Missing OAuth code", 400

        print(f"➡️ Received OAuth code: {code}", flush=True)

        token_payload = {
            "client_id": os.getenv("STRAVA_CLIENT_ID"),
            "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": os.getenv("STRAVA_REDIRECT_URI", "").strip().rstrip(";"),
        }

        print("🚨 Token request payload being sent to Strava:")
        import pprint
        pprint.PrettyPrinter(indent=2).pprint(token_payload)

        athlete_id = store_tokens_from_callback(code, session)
        flask_session["athlete_id"] = athlete_id

        print(f"✅ Stored token and session for athlete_id: {athlete_id}", flush=True)

        if current_app.config.get("TESTING"):
            return f"Token stored for athlete_id: {athlete_id}", 200

        return redirect("/post-oauth?authed=true")

    except requests.exceptions.HTTPError as e:
        print(f"🔥 Callback HTTP error: {e}", flush=True)
        return jsonify({"error": "Strava OAuth token exchange failed"}), 502

    except Exception as e:
        traceback.print_exc()
        return f"❌ Callback error: {str(e)}", 500

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
        rows = session.execute("SELECT athlete_id, expires_at FROM tokens ORDER BY expires_at").fetchall()
        data = [{"athlete_id": r.athlete_id, "expires_at": r.expires_at} for r in rows]
        return jsonify(data), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@auth_bp.route("/profile", methods=["POST"])
def save_athlete_profile():
    from src.db.dao.athlete_dao import upsert_athlete
    session = get_session()
    try:
        data = request.get_json()
        athlete_id = data.get("athlete_id")
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()

        if not athlete_id:
            return jsonify({"error": "Missing athlete_id"}), 400
        if not name and not email:
            return jsonify({"error": "At least one of name or email must be provided"}), 400

        upsert_athlete(session, athlete_id, strava_athlete_id=athlete_id, name=name, email=email)
        return jsonify({"status": "✅ Profile saved"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
