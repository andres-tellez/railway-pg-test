# src/routes/training_plan_routes.py

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import uuid
import json

from src.db.db_session import get_session
from src.db.models import Plan
from src.utils.auth0_jwt import requires_auth
from src.services import training_plan_service
from src.services.training_plan_service import (
    PlanValidationError,
    generate_plan_with_b_plus_validation,
    get_plan_quality_for_user_display,
)
from src.utils.gpt_ops import get_gpt_response

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


# ✅ /api/plan/<id>
@training_plan_bp.route("/<int:plan_id>", methods=["GET"])
def get_plan_route(plan_id):
    import json as json_lib

    with get_session() as session:
        user_id = getattr(g, "user_id", None)
        plan = training_plan_service.get_plan(plan_id, session, user_id)
        if not plan:
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

        # Convert plan to dict and parse segments
        plan_dict = dict(plan)
        if "workouts" in plan_dict:
            for workout in plan_dict["workouts"]:
                workout["segments"] = parse_segments(workout.get("segments"))

        return jsonify(plan_dict), 200


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

        user_profile = (
            session.query(UserProfile).filter_by(user_id=str(user_id)).first()
        )

        if not user_profile:
            return (
                jsonify(
                    {
                        "error": "User profile not found. Please complete your profile first."
                    }
                ),
                404,
            )

        if not user_profile.race_date or not user_profile.race_distance:
            return (
                jsonify(
                    {
                        "error": "Race date and distance not set in profile. Please update your profile first."
                    }
                ),
                400,
            )

        race_date = datetime.strptime(user_profile.race_date, "%Y-%m-%d").date()
        race_distance = user_profile.race_distance.value  # Convert enum to string

        # Use new B+ validation system
        plan = generate_plan_with_b_plus_validation(
            session, user_id, race_date, race_distance
        )

        # Get quality assessment for response
        quality_info = get_plan_quality_for_user_display(plan.id, session)

        session.commit()  # Commit the transaction
        return (
            jsonify(
                {
                    "plan_id": plan.id,
                    "quality": quality_info,
                    "message": "Plan successfully created and validated",
                }
            ),
            201,
        )

    except ValueError as e:
        session.rollback()
        error_msg = str(e)
        # Check if this is a safety-related error
        if (
            "CRITICAL RISK" in error_msg
            or "HIGH RISK" in error_msg
            or "insufficient time" in error_msg.lower()
        ):
            return jsonify({"error": error_msg, "safety_blocked": True}), 400
        else:
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


# ✅ /api/plan/safety-check
@training_plan_bp.route("/safety-check", methods=["POST"])
def check_plan_safety():
    """Check if it's safe to generate a marathon training plan."""
    data = request.get_json() or {}
    user_id_str = data.get("user_id")

    if not user_id_str:
        return jsonify({"error": "user_id is required"}), 400

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return jsonify({"error": "Invalid user_id format"}), 400

    session: Session = get_session()
    try:
        from src.services.training_plan_data_assembler import (
            assemble_training_plan_data,
        )
        from src.db.models.user_profile import UserProfile

        # Check if user profile exists
        user_profile = (
            session.query(UserProfile).filter_by(user_id=str(user_id)).first()
        )
        if not user_profile:
            return (
                jsonify(
                    {
                        "safe": False,
                        "block_plan_creation": True,
                        "show_popup": True,
                        "user_message": "User profile not found. Please complete your profile first.",
                        "risk_level": "CRITICAL",
                    }
                ),
                200,
            )

        # Check if race date and distance are set
        if not user_profile.race_date or not user_profile.race_distance:
            return (
                jsonify(
                    {
                        "safe": False,
                        "block_plan_creation": True,
                        "show_popup": True,
                        "user_message": "Race date and distance not set in profile. Please update your profile first.",
                        "risk_level": "CRITICAL",
                    }
                ),
                200,
            )

        # Assemble training data to assess safety
        data_bundle = assemble_training_plan_data(session, user_id)
        marathon_safety = data_bundle.get("quality_assessment", {}).get(
            "marathon_safety", {}
        )

        # Return safety assessment
        return (
            jsonify(
                {
                    "safe": marathon_safety.get("safe", True),
                    "block_plan_creation": marathon_safety.get(
                        "block_plan_creation", False
                    ),
                    "show_popup": marathon_safety.get("show_popup", False),
                    "user_message": marathon_safety.get("user_message", ""),
                    "risk_level": marathon_safety.get("risk_level", "UNKNOWN"),
                    "reason": marathon_safety.get("reason", ""),
                }
            ),
            200,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return (
            jsonify(
                {
                    "safe": False,
                    "block_plan_creation": True,
                    "show_popup": True,
                    "user_message": "Error checking plan safety. Please try again.",
                    "risk_level": "CRITICAL",
                }
            ),
            200,
        )

    finally:
        session.close()


# Removed unused debug and legacy assessment endpoints - not used by frontend
