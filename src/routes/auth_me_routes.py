# src/routes/auth_me_routes.py
from flask import Blueprint, jsonify, g
from src.utils.auth0_jwt import requires_auth
from src.services.user_identity_service import get_or_create_user_identity

auth_me_bp = Blueprint("auth_me", __name__)


@auth_me_bp.get("/me")
@requires_auth
def me():
    """
    Returns the app's canonical view of the current user
    (after ensuring we have a user_identity row).
    """
    claims = getattr(g, "current_user", {}) or {}
    data = get_or_create_user_identity(claims)
    return jsonify(data), 200
