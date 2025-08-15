from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from src.db.db_session import get_session
from src.db.dao.user_athletes_dao import create_link, get_link_by_user, delete_link

user_link_bp = Blueprint("user_link", __name__)


@user_link_bp.route("/api/user/link", methods=["POST"])
@jwt_required()
def post_link():
    # sub comes from the (mocked) JWT in tests
    sub = get_jwt().get("sub")
    session = get_session()
    try:
        payload = request.get_json() or {}
        athlete_id = payload.get("athlete_id")
        if not athlete_id:
            return jsonify({"error": "Missing athlete_id"}), 400

        row = create_link(session, sub, athlete_id)
        return jsonify({"user_id": row.user_id, "athlete_id": row.athlete_id}), 201
    finally:
        session.close()


@user_link_bp.route("/api/user/link", methods=["GET"])
@jwt_required()
def get_link():
    sub = get_jwt().get("sub")
    session = get_session()
    try:
        row = get_link_by_user(session, sub)
        if not row:
            return jsonify({"error": "Not linked"}), 404
        return jsonify({"user_id": row.user_id, "athlete_id": row.athlete_id}), 200
    finally:
        session.close()


@user_link_bp.route("/api/user/link", methods=["DELETE"])
@jwt_required()
def delete_link_route():
    sub = get_jwt().get("sub")
    session = get_session()
    try:
        deleted = delete_link(session, sub)
        if not deleted:
            return jsonify({"error": "Not linked"}), 404
        return jsonify({"deleted": True}), 200
    finally:
        session.close()
