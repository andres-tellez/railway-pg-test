"""
User Identity Routes Module
===========================

Provides API endpoints for user identity management and user-athlete linking.

Responsibilities:
- User identity CRUD operations
- User-athlete account linking
- User status and profile information
- Integration with Auth0 JWT claims

Endpoints:
----------
GET  /api/user/identity       - Get user identity
POST /api/user/identity       - Create/update user identity
GET  /api/user                - Get user info with status
GET  /api/me                  - Get canonical user view (merged from auth_me_routes.py)
GET  /api/user/link           - Get user-athlete link status
POST /api/user/link           - Link user to athlete
DELETE /api/user/link         - Unlink user from athlete

Dependencies:
-------------
- Auth0 JWT tokens (via @requires_auth decorator)
- User identity DAO (resolve_user_id_from_auth_provider, upsert_identity)
- User athletes DAO (get_by_user_id, create_link, delete_by_user_id)
- User identity service (get_user_status)

Data Managed:
-------------
- UserIdentity table (user_id, email, name, picture, etc.)
- UserAthletes table (user_id <-> athlete_id mapping)

Authentication:
--------------
All endpoints require valid Auth0 JWT token in Authorization header.
The @requires_auth decorator validates tokens and resolves internal user_id.

Note:
-----
The /api/me endpoint was merged from auth_me_routes.py to consolidate
user identity endpoints in a single module.
"""

from __future__ import annotations

from flask import Blueprint, request, g
from sqlalchemy.exc import IntegrityError

from src.utils.auth0_jwt import requires_auth
from src.utils.response_utils import (
    error_response,
    validation_error_response,
    not_found_response,
    success_response,
)

from src.db.models import UserIdentity
from src.db.db_session import db


from src.db.dao.user_athletes_dao import (
    get_by_user_id,
    create_link,
    delete_by_user_id,
)

from src.services.user_identity_service import get_user_status

# Normalize claims
from src.utils.normalize_claims import normalize_claims
from src.db.dao.user_identity_dao import upsert_identity
from datetime import datetime


user_identity_bp = Blueprint("user_identity", __name__, url_prefix="/api")


@user_identity_bp.get("/user/identity")
@requires_auth
def get_user_identity():
    """
    Minimal identity read (no writes). user_id is resolved by @requires_auth.
    """
    user_id = g.user_id
    identity = db.session.get(UserIdentity, user_id)

    if not identity:
        return not_found_response("User")
    return success_response(identity.to_dict())


@user_identity_bp.get("/user/link")
@requires_auth
def get_user_link():
    user_id = g.user_id

    row = get_by_user_id(user_id)
    if not row:
        return not_found_response("User-athlete link")
    return success_response({"linked": True, **row.to_dict()})


@user_identity_bp.post("/user/link")
@requires_auth
def post_user_link():
    user_id = g.user_id

    payload = request.get_json(silent=True) or {}
    try:
        athlete_id = int(payload.get("athlete_id"))
        if athlete_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return validation_error_response(
            "athlete_id must be a positive integer", field="athlete_id"
        )

    try:
        row = create_link(user_id, athlete_id)
        return success_response(
            {"linked": True, "user_id": user_id, "athlete_id": athlete_id},
            status_code=201,
        )
    except IntegrityError:
        return error_response(
            "User or athlete already linked",
            status_code=409,
            error_code="ALREADY_LINKED",
        )


@user_identity_bp.delete("/user/link")
@requires_auth
def delete_user_link():
    user_id = g.user_id

    deleted = delete_by_user_id(user_id)
    if not deleted:
        return not_found_response("User-athlete link")
    return success_response({"deleted": True})


@user_identity_bp.post("/user/identity")
@requires_auth
def save_identity():
    claims = getattr(g, "current_user", {})
    claims = normalize_claims(claims)
    user_id = g.user_id

    payload = {
        "user_id": user_id,
        "email": claims["email"],
        "email_verified": claims["email_verified"],
        "name": claims["name"],
        "picture": claims["picture"],
        "updated_at": datetime.utcnow(),
    }

    result = upsert_identity(payload)
    return success_response({"user_id": str(result)})


@user_identity_bp.get("/user")
@requires_auth
def get_user_info():
    import logging

    logger = logging.getLogger(__name__)

    user_id = g.user_id

    print(
        f"[DEBUG] 📋 GET /api/user - user_id={user_id} (type: {type(user_id).__name__})"
    )
    logger.info(
        f"📋 GET /api/user - user_id={user_id} (type: {type(user_id).__name__})"
    )

    identity = db.session.get(UserIdentity, user_id)
    if not identity:
        return not_found_response("User")

    status = get_user_status(user_id)

    print(
        f"[DEBUG] 📤 GET /api/user response: hasOnboarded={status.get('hasOnboarded')}, hasStrava={status.get('hasStrava')}"
    )
    logger.info(
        f"📤 GET /api/user response: hasOnboarded={status.get('hasOnboarded')}, hasStrava={status.get('hasStrava')}"
    )

    # Get Strava premium status if user has Strava connected
    athlete_link = get_by_user_id(user_id)
    has_strava_premium = None
    if athlete_link and hasattr(athlete_link, "has_strava_premium"):
        has_strava_premium = athlete_link.has_strava_premium

    payload = {
        "name": identity.name or "",
        "email": identity.email or "",
        "picture": identity.picture or "",
        "hasOnboarded": bool(status.get("hasOnboarded")),
        "hasStrava": bool(status.get("hasStrava")),
        "hasActivities": bool(status.get("hasActivities")),
        "hasStravaPremium": has_strava_premium,
    }
    return success_response(payload)


@user_identity_bp.get("/me")
@requires_auth
def me():
    """
    Returns the app's canonical view of the current user.
    Ensures we have a user_identity row (via upsert).
    Uses claims directly from the verified JWT (no /userinfo call).

    This endpoint was merged from auth_me_routes.py.
    """
    claims = getattr(g, "current_user", {}) or {}
    claims = normalize_claims(claims)

    # user_id is already resolved by @requires_auth.
    user_id = g.user_id

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

    return success_response({"user_id": str(result)})
