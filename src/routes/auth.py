# src/routes/auth.py

from flask import Blueprint, request, jsonify
from src.services.auth import login_user, refresh_token, logout_user



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
    """Exchange a refresh token for a new access token."""
    data = request.get_json() or {}
    try:
        new_access = refresh_token(data.get("refresh_token"))
        return jsonify({"access_token": new_access}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Revoke refresh token. Currently a no-op."""
    data = request.get_json() or {}
    logout_user(data.get("refresh_token"))
    return jsonify({"message": "logged out"}), 200
