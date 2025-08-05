# src/routes/health_routes.py

from flask import Blueprint, jsonify
from sqlalchemy import text
from src.db.db_session import get_session

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "db": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "error", "db": "disconnected", "error": str(e)}), 500
