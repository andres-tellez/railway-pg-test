# src/routes/tasktracker_routes.py

from flask import Blueprint, request, jsonify, current_app
from src.utils.jwt_utils import require_auth
from src.db.legacy_sql import get_conn

from src.db.dao.task_dao import (
    get_tasks,
    get_task,
    create_task,
    update_task_status,
    delete_task
)




tasktracker_bp = Blueprint("tasktracker", __name__, url_prefix="/tasks")


@tasktracker_bp.route("/", methods=["POST"])
@require_auth
def create_task_route():
    data = request.get_json() or {}
    if "user_id" not in data or "title" not in data:
        return jsonify({"error": "Missing required fields"}), 400

    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        task_id = create_task(conn, data["user_id"], data["title"], data.get("status", "pending"))
        return jsonify({"id": task_id, "message": "Task created"}), 201
    finally:
        conn.close()


@tasktracker_bp.route("/<int:task_id>", methods=["GET"])
@require_auth
def get_task_route(task_id):
    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        task = get_task(conn, task_id)
        if task:
            return jsonify(task)
        return jsonify({"error": "Task not found"}), 404
    finally:
        conn.close()


@tasktracker_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth
def update_task_route(task_id):
    data = request.get_json() or {}
    if "status" not in data:
        return jsonify({"error": "Missing 'status' field"}), 400

    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        update_task_status(conn, task_id, data["status"])
        return jsonify({"message": "Task updated"}), 200
    finally:
        conn.close()


@tasktracker_bp.route("/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task_route(task_id):
    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        delete_task(conn, task_id)
        return "", 204
    finally:
        conn.close()
