# src/routes/user_identity_routes.py
from __future__ import annotations

import sys
from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError

from src.utils.auth0_jwt import requires_auth

from src.db.models import UserIdentity
from src.db.db_session import db

from src.services.user_identity_service import (
    fetch_userinfo_from_auth0,
    upsert_user_identity_from_userinfo,
    get_user_status,
)

from src.db.dao.user_athletes_dao import (
    get_by_user_id,
    create_link,
    delete_by_user_id,
)

from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider

identity_bp = Blueprint("identity", __name__, url_prefix="/api")


@identity_bp.get("/user/identity")
@requires_auth
def get_user_identity():
    """
    Minimal identity read (no writes). Uses claims to ensure a row exists.
    """
    claims = getattr(g, "current_user", {})
    sub = claims.get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    user_id = resolve_user_id_from_auth_provider(sub, claims)
    identity = db.session.get(UserIdentity, user_id)

    if not identity:
        return {"ok": False, "error": "User not found"}, 404
    return jsonify(identity.to_dict()), 200


@identity_bp.get("/user/link")
@requires_auth
def get_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    user_id = resolve_user_id_from_auth_provider(sub, {})
    row = get_by_user_id(user_id)
    if not row:
        return jsonify({"linked": False}), 404
    return jsonify({"linked": True, **row.to_dict()}), 200


@identity_bp.post("/user/link")
@requires_auth
def post_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        athlete_id = int(payload.get("athlete_id"))
        if athlete_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "athlete_id must be a positive integer"}), 400

    user_id = resolve_user_id_from_auth_provider(sub, {})

    try:
        row = create_link(user_id, athlete_id)
        return (
            jsonify({"linked": True, "user_id": user_id, "athlete_id": athlete_id}),
            201,
        )
    except IntegrityError:
        return jsonify({"error": "user or athlete already linked"}), 409


@identity_bp.delete("/user/link")
@requires_auth
def delete_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    if not sub:
        return jsonify({"deleted": False, "error": "missing_sub"}), 400

    user_id = resolve_user_id_from_auth_provider(sub, {})
    deleted = delete_by_user_id(user_id)
    if not deleted:
        return jsonify({"deleted": False, "message": "no link found"}), 404
    return jsonify({"deleted": True}), 200


@identity_bp.post("/user/identity")
def save_identity():  # 🚨 removed @requires_auth
    print("📬 /user/identity route hit")
    sys.stdout.flush()

    auth = request.headers.get("Authorization", "")
    token = auth.split(" ", 1)[1] if " " in auth else auth

    print(f"🪪 Extracted token (len={len(token)} chars)")
    sys.stdout.flush()

    userinfo = fetch_userinfo_from_auth0(token)
    print("👤 Userinfo from Auth0:", userinfo)
    sys.stdout.flush()

    result = upsert_user_identity_from_userinfo(userinfo)
    print("✅ Upsert result:", result)
    sys.stdout.flush()

    return jsonify(result), 200


@identity_bp.get("/user")
@requires_auth
def get_user_info():
    claims = getattr(g, "current_user", {})
    sub = claims.get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    user_id = resolve_user_id_from_auth_provider(sub)

    if not user_id:
        return jsonify({"error": "User ID could not be resolved"}), 404

    identity = db.session.get(UserIdentity, user_id)
    if not identity:
        return jsonify({"error": "User not found"}), 404

    status = get_user_status(user_id)

    payload = {
        "name": identity.name or "",
        "email": identity.email or "",
        "picture": identity.picture or "",
        "hasOnboarded": bool(status.get("hasOnboarded")),
        "hasStrava": bool(status.get("hasStrava")),
    }
    return jsonify(payload), 200
