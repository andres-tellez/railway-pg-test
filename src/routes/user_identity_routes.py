# src/routes/user_identity_routes.py
from __future__ import annotations

import sys
from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError

from src.utils.auth0_jwt import requires_auth, verify_and_decode

from src.db.models import UserIdentity
from src.db.db_session import db


from src.db.dao.user_athletes_dao import (
    get_by_user_id,
    create_link,
    delete_by_user_id,
)

from src.services.user_identity_service import get_user_status

from src.db.dao.user_identity_dao import resolve_user_id_from_auth_provider

# Normalize claims
from src.utils.normalize_claims import normalize_claims
from src.db.dao.user_identity_dao import upsert_identity
from datetime import datetime


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
@requires_auth
def save_identity():
    claims = getattr(g, "current_user", {})
    sub = claims.get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    claims = normalize_claims(claims)
    user_id = resolve_user_id_from_auth_provider(sub, claims, create_if_missing=True)

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
