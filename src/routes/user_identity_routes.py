# src/routes/user_identity_routes.py
from flask import Blueprint, jsonify, request, g, current_app
from sqlalchemy.exc import IntegrityError
from src.utils.auth0_jwt import requires_auth
from src.db.dao.user_athletes_dao import (
    get_by_user_id,
    create_link,
    delete_by_user_id,
)


identity_bp = Blueprint("identity", __name__, url_prefix="/api")


@identity_bp.get("/user/link")
@requires_auth
def get_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    row = get_by_user_id(sub)
    if not row:
        return jsonify({"linked": False}), 404
    # row is a dict like {"user_id": "...", "athlete_id": 123}
    return jsonify({"linked": True, **row.to_dict()}), 200


@identity_bp.post("/user/link")
@requires_auth
def post_user_link():
    sub = (getattr(g, "current_user", None) or {}).get("sub")
    payload = request.get_json(silent=True) or {}

    # Validate athlete_id
    try:
        athlete_id = int(payload.get("athlete_id"))
        if athlete_id <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "athlete_id must be a positive integer"}), 400

    try:
        row = create_link(
            sub, athlete_id
        )  # expects to return {"user_id": ..., "athlete_id": ...}
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


from src.services.user_identity_service import get_or_create_user_identity


@identity_bp.post("/user/identity")
def save_identity_ping():
    """
    Dev-friendly no-op: accept identity payload and return 200.
    This prevents a 401 from the frontend's PostOAuth step.
    """
    try:
        data = request.get_json(silent=True) or {}
        current_app.logger.info(
            "[identity ping] user_id=%s email=%s",
            data.get("user_id"),
            data.get("email"),
        )
    except Exception:
        pass
    return jsonify({"ok": True}), 200
