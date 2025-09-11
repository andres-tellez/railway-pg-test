# src/routes/auth_me_routes.py
from flask import Blueprint, jsonify, g, request
from src.utils.auth0_jwt import requires_auth

from src.services.user_identity_service import (
    fetch_userinfo_from_auth0,
    upsert_user_identity_from_userinfo,
)

auth_me_bp = Blueprint("auth_me", __name__)


@auth_me_bp.get("/me")
@requires_auth
def me():
    """
    Returns the app's canonical view of the current user.
    Ensures we have a user_identity row (via upsert).
    """
    claims = getattr(g, "current_user", {}) or {}
    auth = request.headers.get("Authorization", "")
    token = auth.split(" ", 1)[1] if " " in auth else auth

    userinfo = fetch_userinfo_from_auth0(token)
    result = upsert_user_identity_from_userinfo(userinfo)
    return jsonify(result), 200
