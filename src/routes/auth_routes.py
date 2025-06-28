from flask import Blueprint, redirect, request, jsonify, session as flask_session
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


# -------- WhoAmI (Session Identity) --------
@auth_bp.route('/whoami', methods=['GET'])
def whoami():
    athlete_id = flask_session.get("athlete_id")
    if not athlete_id:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"athlete_id": athlete_id})


# -------- Admin Login (POST, API) --------
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
                    "exp": datetime.utcnow() + timedelta(seconds=config.ACCESS_TOKEN_EXP)
                },
                config.SECRET_KEY,
                algorithm="HS256"
            )
            refresh_token = jwt.encode(
                {
                    "sub": username,
                    "exp": datetime.utcnow() + timedelta(seconds=config.REFRESH_TOKEN_EXP)
                },
                config.SECRET_KEY,
                algorithm="HS256"
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


# -------- Strava OAuth Login (GET, Browser) --------
@auth_bp.route("/login", methods=["GET"])
def strava_login():
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI")
    client_id = os.getenv("STRAVA_CLIENT_ID")
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&scope=read,activity:read_all"
    )
    return redirect(url)


# -------- Strava OAuth Callback --------
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

        athlete_id = store_tokens_from_callback(code, session)

        flask_session["athlete_id"] = athlete_id  # ✅ store in session

        print(f"✅ Stored token and session for athlete_id: {athlete_id}", flush=True)
        return redirect("/?authed=true")

    except requests.exceptions.HTTPError as e:
        print(f"🔥 Callback HTTP error: {e}", flush=True)
        return jsonify({"error": "Strava OAuth token exchange failed"}), 502

    except Exception as e:
        traceback.print_exc()
        return f"❌ Callback error: {str(e)}", 500

    finally:
        session.close()


# -------- Token Refresh --------
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


# -------- Logout --------
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


# -------- Token Monitoring --------
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
