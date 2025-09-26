from flask import Blueprint, jsonify, g
from datetime import datetime

from src.utils.auth0_jwt import requires_auth
from src.utils.normalize_claims import normalize_claims
from src.db.dao.user_identity_dao import (
    resolve_user_id_from_auth_provider,
    upsert_identity,
)

auth_me_bp = Blueprint("auth_me", __name__)


@auth_me_bp.get("/me")
@requires_auth
def me():
    """
    Returns the app's canonical view of the current user.
    Ensures we have a user_identity row (via upsert).
    Uses claims directly from the verified JWT (no /userinfo call).
    """
    claims = getattr(g, "current_user", {}) or {}
    claims = normalize_claims(claims)
    sub = claims.get("sub")

    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    # 🔑 Resolve a proper UUID for this user
    user_id = resolve_user_id_from_auth_provider(sub, claims, create_if_missing=True)

    # Prepare the payload for upsert
    payload = {
        "user_id": user_id,
        "email": claims["email"],
        "email_verified": claims["email_verified"],
        "name": claims["name"],
        "picture": claims["picture"],
        "updated_at": datetime.utcnow(),
    }

    result = upsert_identity(payload)

    return jsonify({"user_id": str(result)}), 200
