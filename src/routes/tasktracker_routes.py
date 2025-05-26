from flask import Blueprint, request, jsonify, current_app, render_template, abort
import os

from src.utils.jwt_utils import require_auth
from src.db.core import get_engine, get_session
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
    print("📥 Incoming create_task payload:", data)

    if "user_id" not in data or "title" not in data:
        return jsonify({"error": "Missing required fields: user_id, title"}), 400

    session = get_session()
    try:
        task_id = create_task(
            session,
            user_id=data["user_id"],
            title=data["title"],
            status=data.get("status", "pending"),
            milestone=data.get("milestone"),
            labels=data.get("labels"),
            is_icebox=data.get("is_icebox", False),
            details=data.get("details"),
        )
        print("✅ Task created with ID:", task_id)
        return jsonify({"id": task_id, "message": "Task created"}), 201
    except Exception as e:
        print("🔥 CREATE TASK ERROR:", e)
        import traceback
        traceback.print_exc()
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@tasktracker_bp.route("/", methods=["GET"])
@require_auth
def list_tasks_route():
    status = request.args.get("status")
    milestone = request.args.get("milestone")
    label = request.args.get("label")
    is_icebox = request.args.get("is_icebox")
    if is_icebox is not None:
        is_icebox = is_icebox.lower() in ("true", "1", "yes")

    session = get_session()
    try:
        tasks = get_tasks(session, status=status, milestone=milestone, label=label, is_icebox=is_icebox)
        return jsonify(tasks), 200
    finally:
        session.close()


@tasktracker_bp.route("/dashboard", methods=["GET"])
def task_dashboard():
    print("🚨 DASHBOARD DB_URL:", current_app.config.get("DATABASE_URL"), flush=True)
    engine = get_engine()
    session = get_session()

    try:
        tasks = get_tasks(session)
        print(f"🟢 Dashboard sees {len(tasks)} tasks", flush=True)
    except Exception as e:
        print("🔥 Dashboard error:", e, flush=True)
        tasks = []
    finally:
        session.close()

    return render_template("tasks.html", tasks=tasks, filters={})


@tasktracker_bp.route("/<int:task_id>", methods=["GET"])
@require_auth
def get_task_route(task_id):
    session = get_session()
    try:
        task = get_task(session, task_id)
        if task:
            return jsonify(task), 200
        return jsonify({"error": "Task not found"}), 404
    finally:
        session.close()


@tasktracker_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth
def update_task_route(task_id):
    data = request.get_json() or {}
    if not any(k in data for k in ("status", "labels", "is_icebox", "details")):
        return jsonify({"error": "No updatable fields provided"}), 400

    session = get_session()
    try:
        update_task_status(
            session,
            task_id,
            status=data.get("status"),
            labels=data.get("labels"),
            is_icebox=data.get("is_icebox"),
            details=data.get("details"),
        )
        return jsonify({"message": "Task updated"}), 200
    finally:
        session.close()


@tasktracker_bp.route("/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task_route(task_id):
    session = get_session()
    try:
        delete_task(session, task_id)
        return "", 204
    finally:
        session.close()


@tasktracker_bp.route("/debug-dump", methods=["GET"])
def debug_dump():
    if request.headers.get("X-Debug-Key") != os.getenv("DEBUG_KEY"):
        abort(403)

    session = get_session()
    try:
        tasks = get_tasks(session)
        return jsonify(tasks), 200
    finally:
        session.close()
