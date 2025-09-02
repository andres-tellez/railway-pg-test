# src/routes/user_identity_routes.py
from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError

from src.utils.auth0_jwt import requires_auth
from src.db.dao.user_athletes_dao import get_by_user_id, create_link, delete_by_user_id
from src.services.user_identity_service import (
    fetch_userinfo_from_auth0,
    upsert_user_identity_from_userinfo,
    get_or_create_user_identity,
    get_user_status,
)

identity_bp = Blueprint("identity", __name__, url_prefix="/api")


@identity_bp.get("/user/identity")
@requires_auth
def get_user_identity():
    claims = getattr(g, "current_user", {})
    identity = get_or_create_user_identity(claims)
    return jsonify(identity), 200


@identity_bp.get("/user/link")
@requires_auth
def get_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    row = get_by_user_id(sub)
    if not row:
        return jsonify({"linked": False}), 404
    return jsonify({"linked": True, **row.to_dict()}), 200


@identity_bp.post("/user/link")
@requires_auth
def post_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    payload = request.get_json(silent=True) or {}

    try:
        athlete_id = int(payload.get("athlete_id"))
        if athlete_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "athlete_id must be a positive integer"}), 400

    try:
        row = create_link(sub, athlete_id)
        return jsonify({"linked": True, **row}), 201
    except IntegrityError:
        return jsonify({"error": "user or athlete already linked"}), 409


@identity_bp.delete("/user/link")
@requires_auth
def delete_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    deleted = delete_by_user_id(sub)
    if not deleted:
        return jsonify({"deleted": False, "message": "no link found"}), 404
    return jsonify({"deleted": True}), 200


@identity_bp.post("/user/identity")
@requires_auth
def save_identity():
    """Fetch profile from Auth0 and upsert."""
    auth = request.headers.get("Authorization", "")
    token = auth.split(" ", 1)[1] if " " in auth else auth
    userinfo = fetch_userinfo_from_auth0(token)
    result = upsert_user_identity_from_userinfo(userinfo)
    return jsonify(result), 200


@identity_bp.get("/user")
@requires_auth
def get_user_info():
    claims = getattr(g, "current_user", {})
    get_or_create_user_identity(claims)
    result = get_user_status(claims.get("sub"))
    return jsonify(result), 200
