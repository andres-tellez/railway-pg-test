# src/routes/auth.py

from flask import Blueprint, request, jsonify
from src.services.auth import login_user, logout_user, refresh_token

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and issue access + refresh tokens."""
    data = request.get_json() or {}
    try:
        access, refresh = login_user(data)
        return jsonify({
            "access_token": access,
            "refresh_token": refresh
        }), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 401


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Issue new access token using a refresh token from Authorization header."""
    auth_header = request.headers.get("Authorization", None)
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(" ")[1]
    try:
        new_token = refresh_token(token)
        return jsonify({"access_token": new_token}), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 401


@auth_bp.route("/logout", methods=["POST"])_
