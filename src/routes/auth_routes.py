# src/routes/auth_routes.py

from flask import Blueprint, redirect, request, jsonify
import traceback
import requests
from datetime import datetime, timedelta
import jwt

import src.utils.config as config
from src.services.token_service import (
    get_authorization_url,
    store_tokens_from_callback,
    refresh_token_if_expired,
    delete_athlete_tokens
)
from src.db.db_session import get_session

auth_bp = Blueprint("auth", __name__)


# -------- Admin Login (Basic) --------
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


# -------- Strava OAuth Flow --------
@auth_bp.route("/callback")
def callback():
    session = get_session()
    try:
        code = request.args.get("code")
        if not code:
            return "❌ Missing OAuth code", 400

        athlete_id = store_tokens_from_callback(code, session)
        return f"✅ Token stored for athlete_id: {athlete_id}", 200

    except requests.exceptions.HTTPError as http_err:
        if http_err.response and http_err.response.status_code == 400:
            return jsonify({"error": "Invalid OAuth code or bad request"}), 401
        traceback.print_exc()
        return jsonify({"error": str(http_err)}), 502
    except KeyError:
        traceback.print_exc()
        return "❌ Strava callback data incomplete", 502
    except Exception as e:
        traceback.print_exc()
        return f"❌ Callback error: {str(e)}", 500
    finally:
        session.close()


# -------- Token Operations --------
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
