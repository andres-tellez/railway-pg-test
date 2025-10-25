# src/routes/plan_routes.py

from flask import Blueprint, jsonify, g, request
from sqlalchemy.orm import Session, joinedload
import uuid

from src.db.db_session import get_session
from src.db.models.plans import Plan
from src.utils.auth0_jwt import requires_auth
from src.db.dao.plans_dao import (
    get_plan_with_workouts,
    list_plans_for_user,
    get_active_plan,
    set_plan_active,
    delete_plan,
)

plan_bp = Blueprint("plan", __name__, url_prefix="/api/plan")


# Inject user_id for local testing (if not using Auth0 yet)
@plan_bp.before_request
def inject_user_id():
    user_id = request.headers.get("X-User-Id")
    if user_id:
        try:
            g.user_id = uuid.UUID(user_id)
        except ValueError:
            g.user_id = None


# ✅ /api/plan/current — get current active plan (read-only)
@plan_bp.route("/current", methods=["GET"])
@requires_auth
def get_current_plan():
    user_id = g.user_id

    with get_session() as session:
        # Get the active plan with workouts
        plan = (
            session.query(Plan)
            .options(joinedload(Plan.workouts))
            .filter_by(user_id=user_id, is_active=True)
            .first()
        )

        # Fallback: if no active plan, get the most recent one
        if not plan:
            plan = (
                session.query(Plan)
                .options(joinedload(Plan.workouts))
                .filter_by(user_id=user_id)
                .order_by(Plan.created_at.desc())
                .first()
            )

        if not plan:
            return jsonify({"error": "No plan found"}), 404

        workouts = sorted(plan.workouts, key=lambda w: w.date)

        # Helper to convert segments from {warmup, main, cooldown} to array format
        def parse_segments(segments_json):
            if not segments_json:
                return []
            try:
                import json

                segments = (
                    json.loads(segments_json)
                    if isinstance(segments_json, str)
                    else segments_json
                )
                result = []

                # Handle warmup
                warmup = segments.get("warmup", {})
                if warmup:
                    result.append(
                        {
                            "name": "Warmup",
                            "distance": (
                                warmup.get("distance", "")
                                if isinstance(warmup, dict)
                                else ""
                            ),
                            "target_zone": (
                                warmup.get("target", "")
                                if isinstance(warmup, dict)
                                else ""
                            ),
                            "notes": (
                                warmup.get("notes", warmup)
                                if isinstance(warmup, dict)
                                else warmup
                            ),
                        }
                    )

                # Handle main
                main = segments.get("main", {})
                if main:
                    result.append(
                        {
                            "name": "Main",
                            "distance": (
                                main.get("distance", "")
                                if isinstance(main, dict)
                                else ""
                            ),
                            "target_zone": (
                                main.get("target", "") if isinstance(main, dict) else ""
                            ),
                            "notes": (
                                main.get("notes", main)
                                if isinstance(main, dict)
                                else main
                            ),
                        }
                    )

                # Handle cooldown
                cooldown = segments.get("cooldown", {})
                if cooldown:
                    result.append(
                        {
                            "name": "Cooldown",
                            "distance": (
                                cooldown.get("distance", "")
                                if isinstance(cooldown, dict)
                                else ""
                            ),
                            "target_zone": (
                                cooldown.get("target", "")
                                if isinstance(cooldown, dict)
                                else ""
                            ),
                            "notes": (
                                cooldown.get("notes", cooldown)
                                if isinstance(cooldown, dict)
                                else cooldown
                            ),
                        }
                    )

                return result
            except:
                return []

        return (
            jsonify(
                {
                    "plan_id": plan.id,
                    "start_date": workouts[0].date.isoformat() if workouts else None,
                    "race_date": plan.race_date.isoformat() if plan.race_date else None,
                    "notes": plan.notes,
                    "workouts": [
                        {
                            "date": w.date.isoformat(),
                            "workout_type": w.workout_type,
                            "intensity": w.intensity,
                            "description": w.description,
                            "miles": w.miles,
                            "target_zone": w.target_zone,
                            "target_hr": w.target_hr,
                            "focus": w.focus,
                            "segments": parse_segments(w.segments),
                        }
                        for w in workouts
                    ],
                }
            ),
            200,
        )


# ✅ /api/plan/<id> — get specific plan by ID (read-only)
@plan_bp.route("/<int:plan_id>", methods=["GET"])
def get_plan_route(plan_id):
    import json as json_lib

    with get_session() as session:
        user_id = getattr(g, "user_id", None)
        plan_data = get_plan_with_workouts(
            session, plan_id, str(user_id) if user_id else None
        )

        if not plan_data:
            return jsonify({"error": "Plan not found"}), 404

        # Parse segments for frontend compatibility
        def parse_segments(segments_json):
            if not segments_json:
                return []
            try:
                segments = (
                    json_lib.loads(segments_json)
                    if isinstance(segments_json, str)
                    else segments_json
                )
                result = []

                # Handle warmup
                warmup = segments.get("warmup", {})
                if warmup:
                    result.append(
                        {
                            "name": "Warmup",
                            "distance": (
                                warmup.get("distance", "")
                                if isinstance(warmup, dict)
                                else ""
                            ),
                            "target_zone": (
                                warmup.get("target", "")
                                if isinstance(warmup, dict)
                                else ""
                            ),
                            "notes": (
                                warmup.get("notes", warmup)
                                if isinstance(warmup, dict)
                                else warmup
                            ),
                        }
                    )

                # Handle main
                main = segments.get("main", {})
                if main:
                    result.append(
                        {
                            "name": "Main",
                            "distance": (
                                main.get("distance", "")
                                if isinstance(main, dict)
                                else ""
                            ),
                            "target_zone": (
                                main.get("target", "") if isinstance(main, dict) else ""
                            ),
                            "notes": (
                                main.get("notes", main)
                                if isinstance(main, dict)
                                else main
                            ),
                        }
                    )

                # Handle cooldown
                cooldown = segments.get("cooldown", {})
                if cooldown:
                    result.append(
                        {
                            "name": "Cooldown",
                            "distance": (
                                cooldown.get("distance", "")
                                if isinstance(cooldown, dict)
                                else ""
                            ),
                            "target_zone": (
                                cooldown.get("target", "")
                                if isinstance(cooldown, dict)
                                else ""
                            ),
                            "notes": (
                                cooldown.get("notes", cooldown)
                                if isinstance(cooldown, dict)
                                else cooldown
                            ),
                        }
                    )

                return result
            except:
                return []

        # Parse segments for each workout
        if "workouts" in plan_data:
            for workout in plan_data["workouts"]:
                workout["segments"] = parse_segments(workout.get("segments"))

        return jsonify(plan_data), 200


# ✅ /api/plan/list — get all plans for user
@plan_bp.route("/list", methods=["GET"])
@requires_auth
def list_user_plans():
    """Get all training plans for the current user."""
    user_id = g.user_id

    with get_session() as session:
        plans = list_plans_for_user(session, str(user_id))

        return (
            jsonify(
                {
                    "plans": [
                        {
                            "id": plan.id,
                            "plan_name": plan.plan_name,
                            "race_date": (
                                plan.race_date.isoformat() if plan.race_date else None
                            ),
                            "race_distance": plan.race_distance,
                            "created_at": (
                                plan.created_at.isoformat() if plan.created_at else None
                            ),
                            "is_active": plan.is_active,
                        }
                        for plan in plans
                    ]
                }
            ),
            200,
        )


# ✅ /api/plan/<id>/set-active — set a plan as active
@plan_bp.route("/<int:plan_id>/set-active", methods=["POST"])
@requires_auth
def set_active_plan(plan_id):
    """Set a specific plan as active."""
    user_id = g.user_id

    with get_session() as session:
        success = set_plan_active(session, plan_id, str(user_id))

        if not success:
            return jsonify({"error": "Plan not found or unauthorized"}), 404

        return jsonify({"message": "Plan activated successfully"}), 200


# ✅ /api/plan/<id> — delete a plan
@plan_bp.route("/<int:plan_id>", methods=["DELETE"])
@requires_auth
def delete_user_plan(plan_id):
    """Delete a training plan."""
    user_id = g.user_id

    with get_session() as session:
        success = delete_plan(session, plan_id, str(user_id))

        if not success:
            return jsonify({"error": "Plan not found or unauthorized"}), 404

        return jsonify({"message": "Plan deleted successfully"}), 200
