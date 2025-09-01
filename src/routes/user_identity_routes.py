# src/routes/user_identity_routes.py

from flask import Blueprint, jsonify, request, g, current_app
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert
import requests

from src.utils.auth0_jwt import requires_auth

from src.db.db_session import db
from src.db.models import UserIdentity
from src.utils import config
from src.db.dao.user_athletes_dao import (
    get_by_user_id,
    create_link,
    delete_by_user_id,
)

identity_bp = Blueprint("identity", __name__, url_prefix="/api")


# === Auth0 userinfo helper ===
def fetch_userinfo_from_auth0(token: str) -> dict:
    resp = requests.get(
        f"https://{config.AUTH0_DOMAIN}/userinfo",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()


# === GET route to return full user identity (name, email, picture, etc) ===
#    This gives you all user details for the dashboard.


@identity_bp.get("/user/identity")
@requires_auth
def get_user_identity():
    claims = getattr(g, "current_user", {})
    identity = get_or_create_user_identity(claims)
    return jsonify(identity), 200


# === GET /user/link ===
@identity_bp.get("/user/link")
@requires_auth
def get_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    row = get_by_user_id(sub)
    if not row:
        return jsonify({"linked": False}), 404
    return jsonify({"linked": True, **row.to_dict()}), 200


# === POST /user/link ===
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


# === DELETE /user/link ===
@identity_bp.delete("/user/link")
@requires_auth
def delete_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    deleted = delete_by_user_id(sub)
    if not deleted:
        return jsonify({"deleted": False, "message": "no link found"}), 404
    return jsonify({"deleted": True}), 200


# === POST /user/identity ===
@identity_bp.post("/user/identity")
@requires_auth
def save_identity():
    """
    Fetch full user profile from Auth0 and upsert into user_identity table.
    """
    token = request.headers.get("Authorization", "").split(" ")[1]
    userinfo = fetch_userinfo_from_auth0(token)

    user_id = userinfo["sub"]
    email = userinfo.get("email")
    email_verified = userinfo.get("email_verified")
    name = userinfo.get("name")
    picture = userinfo.get("picture")

    stmt = (
        pg_insert(UserIdentity)
        .values(
            user_id=user_id,
            email=email,
            email_verified=email_verified,
            name=name,
            picture=picture,
        )
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "email": email,
                "email_verified": email_verified,
                "name": name,
                "picture": picture,
            },
        )
    )

    db.session.execute(stmt)
    db.session.commit()

    return jsonify({"ok": True, "user_id": user_id})


# === GET /user ===
from src.services.user_identity_service import (
    get_or_create_user_identity,
    get_user_status,
)


@identity_bp.get("/user")
@requires_auth
def get_user_info():
    claims = getattr(g, "current_user", {})
    get_or_create_user_identity(claims)
    result = get_user_status(claims.get("sub"))
    return jsonify(result), 200
