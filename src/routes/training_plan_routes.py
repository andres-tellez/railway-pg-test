# src/routes/training_plan_routes.py

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import uuid

from src.db.db_session import get_session
from src.db.models import Plan
from src.utils.auth0_jwt import requires_auth
from src.services import training_plan_service
from src.services.training_plan_service import (
    PlanValidationError,
    build_training_plan_prompt,
)

training_plan_bp = Blueprint("training_plan", __name__, url_prefix="/api/plan")


# Inject user_id for local testing (if not using Auth0 yet)
@training_plan_bp.before_request
def inject_user_id():
    user_id = request.headers.get("X-User-Id")
    if user_id:
        try:
            g.user_id = uuid.UUID(user_id)
        except ValueError:
            g.user_id = None


# ✅ /api/plan/current — secure current user plan
@training_plan_bp.route("/current", methods=["GET"])
@requires_auth
def get_current_plan():
    user_id = g.user_id

    with get_session() as session:
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

        return (
            jsonify(
                {
                    "plan_id": plan.id,
                    "start_date": workouts[0].date.isoformat() if workouts else None,
                    "race_date": plan.race_date.isoformat() if plan.race_date else None,
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
                            "segments": w.segments,
                        }
                        for w in workouts
                    ],
                }
            ),
            200,
        )


# ✅ /api/plan/<id>
@training_plan_bp.route("/<int:plan_id>", methods=["GET"])
def get_plan_route(plan_id):
    with get_session() as session:
        user_id = getattr(g, "user_id", None)
        plan = training_plan_service.get_plan(plan_id, session, user_id)
        if not plan:
            return jsonify({"error": "Plan not found"}), 404
        return jsonify(plan), 200


# ✅ /api/plan/generate
@training_plan_bp.route("/generate", methods=["POST"])
def generate_plan_route():
    data = request.get_json() or {}
    user_id_str = data.get("user_id")  # TEMP: will replace with Auth0 `g.user_id`

    if not user_id_str:
        return (
            jsonify({"error": "user_id is required"}),
            400,
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return jsonify({"error": "Invalid user_id format"}), 400

    session: Session = get_session()
    try:
        # Get race data from user_profile instead of frontend
        from src.db.models.user_profile import UserProfile
        user_profile = session.query(UserProfile).filter_by(user_id=str(user_id)).first()
        
        if not user_profile:
            return jsonify({"error": "User profile not found. Please complete your profile first."}), 404
            
        if not user_profile.race_date or not user_profile.race_distance:
            return jsonify({"error": "Race date and distance not set in profile. Please update your profile first."}), 400
            
        race_date = datetime.strptime(user_profile.race_date, "%Y-%m-%d").date()
        race_distance = user_profile.race_distance.value  # Convert enum to string
        
        plan = training_plan_service.generate_plan(
            session, user_id, race_date, race_distance
        )
        session.commit()  # Commit the transaction
        return jsonify({"plan_id": plan.id}), 201

    except ValueError:
        session.rollback()
        return jsonify({"error": "User not found"}), 404

    except PlanValidationError as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        import traceback

        traceback.print_exc()
        session.rollback()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        session.close()


# ✅ Debugging endpoints
@training_plan_bp.route("/debug/activities")
def debug_activities():
    from src.services.training_plan_data_assembler import load_recent_activities

    session = get_session()
    try:
        data = load_recent_activities(session)
        return jsonify(data), 200
    finally:
        session.close()


@training_plan_bp.route("/debug/plan-data")
def debug_training_plan_data():
    from src.services.training_plan_data_assembler import assemble_training_plan_data

    user_id_str = request.args.get("user_id")
    if not user_id_str:
        return jsonify({"error": "Missing user_id param"}), 400

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return jsonify({"error": "Invalid UUID"}), 400

    session = get_session()
    try:
        result = assemble_training_plan_data(session, user_id)
        prompt = build_training_plan_prompt(result)
        return (
            jsonify(
                {
                    "user_profile": result.get("user_profile"),
                    "weekly_summaries": result.get("weekly_summaries"),
                    "activities": result.get("activities"),
                    "prompt_preview": prompt,
                }
            ),
            200,
        )
    finally:
        session.close()


@training_plan_bp.route("/debug/weekly-summaries")
@requires_auth
def debug_weekly_summaries():
    from src.services.training_plan_data_assembler import (
        load_recent_activities,
        summarize_weekly_training,
    )

    user_id = g.user_id  # ✅ use Auth0-derived user ID
    session = get_session()
    try:
        activities = load_recent_activities(session, user_id=user_id)
        summaries = summarize_weekly_training(activities)
        return jsonify({"summaries": summaries}), 200
    finally:
        session.close()
