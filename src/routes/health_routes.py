"""
Health Check Routes Module
==========================

Provides health check endpoints for monitoring system status.

Endpoints:
----------
GET /health
    Basic health check including database connectivity

Response Format:
---------------
{
    "status": "ok" | "error",
    "db": "connected" | "disconnected",
    "error": "<error message>" (if error)
}

Dependencies:
-------------
- Database: PostgreSQL connection via db_session

Usage:
------
Used by monitoring systems, load balancers, and deployment pipelines
to verify the application is running and database is accessible.

Note:
-----
This endpoint does not require authentication as it's used for
infrastructure monitoring.
"""

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
