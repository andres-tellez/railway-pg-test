# src/routes/tasktracker_routes.py

from flask import Blueprint, request, jsonify, current_app, render_template
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
        return jsonify({"error": "Missing required fields: user_id, title"}), 400

    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        task_id = create_task(
            conn,
            user_id=data["user_id"],
            title=data["title"],
            status=data.get("status", "pending"),
            milestone=data.get("milestone"),
            labels=data.get("labels"),
            is_icebox=data.get("is_icebox", False),
        )
        return jsonify({"id": task_id, "message": "Task created"}), 201
    finally:
        conn.close()


@tasktracker_bp.route("/", methods=["GET"])
@require_auth
def list_tasks_route():
    status = request.args.get("status")
    milestone = request.args.get("milestone")
    label = request.args.get("label")
    is_icebox = request.args.get("is_icebox")
    if is_icebox is not None:
        is_icebox = is_icebox.lower() in ("true", "1", "yes")

    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        tasks = get_tasks(conn, status=status, milestone=milestone, label=label, is_icebox=is_icebox)
        return jsonify(tasks), 200
    finally:
        conn.close()


@tasktracker_bp.route("/dashboard", methods=["GET"])
def task_dashboard():
    status = request.args.get("status")
    milestone = request.args.get("milestone")
    label = request.args.get("label")
    icebox = request.args.get("icebox")
    is_icebox = icebox.lower() == "true" if icebox else None

    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        tasks = get_tasks(conn, status=status, milestone=milestone, label=label, is_icebox=is_icebox)
    finally:
        conn.close()

    return render_template("tasks.html", tasks=tasks, filters={
        "status": status,
        "milestone": milestone,
        "label": label,
        "icebox": icebox,
    })


@tasktracker_bp.route("/<int:task_id>", methods=["GET"])
@require_auth
def get_task_route(task_id):
    db_url = current_app.config.get("DATABASE_URL")
    conn = get_conn(db_url)
    try:
        task = get_task(conn, task_id)
        if task:
            return jsonify(task), 200
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
