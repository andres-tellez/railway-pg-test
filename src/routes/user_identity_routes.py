# src/routes/user_identity_routes.py
from __future__ import annotations

import sys
from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import IntegrityError

from src.utils.auth0_jwt import requires_auth

from src.services.user_identity_service import (
    fetch_userinfo_from_auth0,
    upsert_user_identity_from_userinfo,
    get_or_create_user_identity,
    get_user_status,
    resolve_user_id_from_auth_provider,  # ✅ map sub -> internal UUID
)

# If you want to keep the explicit link endpoints, import the DAO
from src.db.dao.user_athletes_dao import (
    get_by_user_id,
    create_link,
    delete_by_user_id,
)

identity_bp = Blueprint("identity", __name__, url_prefix="/api")


@identity_bp.get("/user/identity")
@requires_auth
def get_user_identity():
    """
    Minimal identity read (no writes). Uses claims to ensure a row exists.
    """
    claims = getattr(g, "current_user", {}) or {}
    identity = get_or_create_user_identity(claims)
    return jsonify(identity), 200


# -------- Optional user<->athlete link management (manual) --------
# These endpoints DO NOT run automatically during auth; they are explicit admin/user actions.


@identity_bp.get("/user/link")
@requires_auth
def get_user_link():
    """
    Return current link for the logged-in user.
    NOTE: map Auth0 sub -> internal UUID before reading user_athletes.
    """
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    user_id = resolve_user_id_from_auth_provider(sub)  # UUID
    row = get_by_user_id(user_id)
    if not row:
        return jsonify({"linked": False}), 404
    return jsonify({"linked": True, **row.to_dict()}), 200


@identity_bp.post("/user/link")
@requires_auth
def post_user_link():
    """
    Create/update a link for the logged-in user.
    Body: { "athlete_id": <int> }
    """
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

    user_id = resolve_user_id_from_auth_provider(sub)  # UUID

    try:
        # Your DAO should expect internal UUID here
        row = create_link(user_id, athlete_id)
        # row may be a model or dict depending on DAO; normalize response:
        return (
            jsonify({"linked": True, "user_id": user_id, "athlete_id": athlete_id}),
            201,
        )
    except IntegrityError:
        return jsonify({"error": "user or athlete already linked"}), 409


@identity_bp.delete("/user/link")
@requires_auth
def delete_user_link():
    """
    Delete the current link for the logged-in user.
    """
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    if not sub:
        return jsonify({"deleted": False, "error": "missing_sub"}), 400

    user_id = resolve_user_id_from_auth_provider(sub)  # UUID
    deleted = delete_by_user_id(user_id)
    if not deleted:
        return jsonify({"deleted": False, "message": "no link found"}), 404
    return jsonify({"deleted": True}), 200


# -------- Identity upsert (Auth0 userinfo -> our DB) --------


@identity_bp.post("/user/identity")
@requires_auth
def save_identity():
    """
    Pull Auth0 /userinfo and upsert:
    - user_identity (email/name/picture, etc.)
    - user_auth_providers (sub mapping -> internal user_id)
    Does NOT touch user_athletes.
    """
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


# -------- Dashboard-friendly user blob --------


@identity_bp.get("/user")
@requires_auth
def get_user_info():
    """
    Return the merged user blob the dashboard expects:
      {
        name, email, picture,
        hasOnboarded: bool,
        hasStrava: bool
      }

    Key point: we must resolve Auth0 `sub` -> internal UUID BEFORE we call DB
    helpers that expect the UUID (e.g., user_athletes).
    """
    claims = getattr(g, "current_user", {}) or {}
    sub = claims.get("sub")
    if not sub:
        return jsonify({"error": "missing_sub"}), 400

    # Ensure we have a user_identity row and get its basics
    identity = get_or_create_user_identity(
        claims
    )  # returns dict (name/email/picture...)

    # IMPORTANT: Map to our internal UUID for downstream checks
    user_id = resolve_user_id_from_auth_provider(sub)

    # hasOnboarded/hasStrava come from DB using internal UUID
    status = get_user_status(user_id)

    payload = {
        "name": identity.get("name") or "",
        "email": identity.get("email") or "",
        "picture": identity.get("picture") or "",
        "hasOnboarded": bool(status.get("hasOnboarded")),
        "hasStrava": bool(status.get("hasStrava")),
    }
    return jsonify(payload), 200
