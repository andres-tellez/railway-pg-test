# src/routes/admin_routes.py

from flask import Blueprint, jsonify, request, current_app
from src.db.core import get_session
from src.db.dao.task_dao import (
    get_tasks, get_task, create_task, update_task_status, delete_task
)
from src.utils.jwt_utils import require_auth

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/debug-dump", methods=["GET"])
@require_auth
def dump_tasks():
    session = get_session()
    try:
        tasks = get_tasks(session)
        return jsonify(tasks), 200
    finally:
        session.close()


@admin_bp.route("/debug-load", methods=["POST"])
@require_auth
def load_tasks():
    payload = request.get_json()
    if not isinstance(payload, list):
        return jsonify({"error": "Expected a list of tasks"}), 400

    session = get_session()
    inserted = []
    try:
        for task in payload:
            task_id = create_task(
                session,
                user_id=task["user_id"],
                title=task["title"],
                status=task.get("status", "pending"),
                milestone=task.get("milestone"),
                labels=task.get("labels"),
                is_icebox=task.get("is_icebox", False),
                details=task.get("details"),
            )
            inserted.append(task_id)
        session.commit()  # ✅ commit the batch insert
        return jsonify({"inserted_ids": inserted}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@admin_bp.route("/proxy-command", methods=["POST"])
@require_auth
def proxy_command():
    if request.user.get("user_id") != "internal":
        return jsonify({"error": "Unauthorized"}), 403

    payload = request.get_json() or {}
    action = payload.get("action")
    args = payload.get("args", {})

    session = get_session()
    try:
        if action == "get_tasks":
            return jsonify(get_tasks(session, **args))
        elif action == "create_task":
            task_id = create_task(session, **args)
            session.commit()
            return jsonify({"id": task_id})
        elif action == "update_task":
            update_task_status(session, **args)
            session.commit()
            return jsonify({"updated": True})
        elif action == "delete_task":
            delete_task(session, **args)
            session.commit()
            return jsonify({"deleted": True})
        elif action == "truncate_tasks":
            session.execute("TRUNCATE TABLE tasks RESTART IDENTITY CASCADE;")
            session.commit()
            return jsonify({"status": "tasks table truncated"})
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@admin_bp.route("/debug-wipe", methods=["POST"])
def wipe_tasks():
    internal_key = request.headers.get("X-Internal-Key")
    expected = current_app.config.get("INTERNAL_API_KEY")
    if internal_key != expected:
        return jsonify({"error": "Unauthorized"}), 403

    session = get_session()
    try:
        session.execute("DELETE FROM tasks;")
        session.commit()
        return jsonify({"message": "All tasks deleted"}), 200
    finally:
        session.close()


@admin_bp.route("/debug-truncate", methods=["POST"])
@require_auth
def truncate_tasks():
    if not request.user.get("is_internal"):
        return jsonify({"error": "Unauthorized"}), 403

    session = get_session()
    try:
        session.execute("TRUNCATE TABLE tasks RESTART IDENTITY CASCADE;")
        session.commit()
        return jsonify({"message": "Tasks table truncated"}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

