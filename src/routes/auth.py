# src/routes/auth.py

from flask import Blueprint, request, jsonify, current_app
from src.services.auth import login_user, logout_user
import jwt
from datetime import datetime, timedelta

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and issue access + refresh tokens."""
    data = request.get_json() or {}
    try:
        access, refresh = login_user(data)
        return jsonify({"access_token": access, "refresh_token": refresh}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 401


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Issue new access token using refresh token from Authorization header."""
    auth_header = request.headers.get("Authorization", None)
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"], options={"verify_exp": False})
        user_id = payload.get("sub")
        if not user_id:
            return jsonify({"error": "Invalid token payload"}), 401

        new_token = jwt.encode({
            "sub": user_id,
            "exp": datetime.utcnow() + timedelta(hours=1)
        }, current_app.config["SECRET_KEY"], algorithm="HS256")

        return jsonify({"access_token": new_token})
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Revoke refresh token. Currently a no-op."""
    data = request.get_json() or {}
    logout_user(data.get("refresh_token"))
    return jsonify({"message": "logged out"}), 200
