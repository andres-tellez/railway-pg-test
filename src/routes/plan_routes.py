# src/routes/plan_routes.py

from flask import Blueprint, jsonify, g, request
from sqlalchemy.orm import joinedload
import uuid
import logging

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
from src.schemas.plan_schema import PlanCreateSchema
from datetime import datetime, date, timedelta
from src.utils.timezone_helpers import resolve_timezone
from src.routes.plan_generation_v2 import (
    run_v2_plan_generation,
    build_standard_draft_payload,
)

logger = logging.getLogger(__name__)

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

        # Helper to parse segments - supports both new spec-compliant format and legacy format
        def parse_segments(segments_json):
            if not segments_json:
                return None

            try:
                import json

                segments = (
                    json.loads(segments_json)
                    if isinstance(segments_json, str)
                    else segments_json
                )

                # Check if it's the new spec-compliant format (has "steps" array)
                if isinstance(segments, dict) and "steps" in segments:
                    # New format: {steps: [...], units: "...", targetType: "...", notes: "..."}
                    # Return as-is for frontend compatibility
                    return segments

                # Legacy format: {warmup: {...}, main: {...}, cooldown: {...}}
                # Convert to new format for compatibility
                if isinstance(segments, dict) and (
                    "warmup" in segments or "main" in segments or "cooldown" in segments
                ):
                    steps = []

                    # Handle warmup
                    warmup = segments.get("warmup", {})
                    if warmup:
                        steps.append(
                            {
                                "name": "Warm-up",
                                "value": (
                                    warmup.get("distance", 0)
                                    if isinstance(warmup, dict)
                                    else 0
                                ),
                                "durationType": "DISTANCE",
                                "target": (
                                    warmup.get("target", {})
                                    if isinstance(warmup, dict)
                                    else {}
                                ),
                                "intensity": "EASY",
                            }
                        )

                    # Handle main
                    main = segments.get("main", {})
                    if main:
                        steps.append(
                            {
                                "name": "Main",
                                "value": (
                                    main.get("distance", 0)
                                    if isinstance(main, dict)
                                    else 0
                                ),
                                "durationType": "DISTANCE",
                                "target": (
                                    main.get("target", {})
                                    if isinstance(main, dict)
                                    else {}
                                ),
                                "intensity": "STEADY",
                            }
                        )

                    # Handle cooldown
                    cooldown = segments.get("cooldown", {})
                    if cooldown:
                        steps.append(
                            {
                                "name": "Cool-down",
                                "value": (
                                    cooldown.get("distance", 0)
                                    if isinstance(cooldown, dict)
                                    else 0
                                ),
                                "durationType": "DISTANCE",
                                "target": (
                                    cooldown.get("target", {})
                                    if isinstance(cooldown, dict)
                                    else {}
                                ),
                                "intensity": "EASY",
                            }
                        )

                    # Return in new format
                    return {
                        "steps": steps,
                        "units": "mi",
                        "targetType": "PACE",
                        "notes": segments.get("notes", ""),
                    }

                # If it's already an array or unknown format, return None
                return None
            except Exception as e:
                logger.warning(f"Failed to parse segments: {e}")
                return None

        # Calculate HR zones on-the-fly if missing
        from src.db.dao.user_profile_dao import get_user_profile
        from src.services.training_plan.plan_storage_service import PlanStorageService

        user_profile = get_user_profile(session, user_id)

        workouts_data = []
        for w in workouts:
            target_hr = w.target_hr
            # Calculate HR zone if missing
            if not target_hr and w.run_type_key:
                target_hr = PlanStorageService._calculate_hr_zone(
                    w.run_type_key, user_profile
                )
            elif not target_hr:
                # Try to infer from workout_type
                workout_type_lower = (w.workout_type or "").lower()
                if "threshold" in workout_type_lower or "tempo" in workout_type_lower:
                    run_type_key = "threshold"
                elif "steady" in workout_type_lower or "aerobic" in workout_type_lower:
                    run_type_key = "steady"
                elif "long" in workout_type_lower or "endurance" in workout_type_lower:
                    run_type_key = "long"
                elif "easy" in workout_type_lower or "recovery" in workout_type_lower:
                    run_type_key = "easy"
                else:
                    run_type_key = "easy"  # default
                target_hr = PlanStorageService._calculate_hr_zone(
                    run_type_key, user_profile
                )

            workouts_data.append(
                {
                    "date": w.date.isoformat(),
                    "workout_type": w.workout_type,
                    "intensity": w.intensity,
                    "description": w.description,
                    "miles": w.miles,
                    "target_zone": w.target_zone,
                    "target_hr": target_hr,
                    "focus": w.focus,
                    "segments": parse_segments(w.segments),
                    "phase": w.phase,  # Include phase from database
                }
            )

        return (
            jsonify(
                {
                    "plan_id": plan.id,
                    "start_date": workouts[0].date.isoformat() if workouts else None,
                    "race_date": plan.race_date.isoformat() if plan.race_date else None,
                    "race_distance": plan.race_distance,  # Include race distance for frontend
                    "notes": plan.notes,
                    "workouts": workouts_data,
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

        # Helper to parse segments - supports both new spec-compliant format and legacy format
        def parse_segments(segments_json):
            if not segments_json:
                return None

            try:
                segments = (
                    json_lib.loads(segments_json)
                    if isinstance(segments_json, str)
                    else segments_json
                )

                # Check if it's the new spec-compliant format (has "steps" array)
                if isinstance(segments, dict) and "steps" in segments:
                    # New format: {steps: [...], units: "...", targetType: "...", notes: "..."}
                    # Return as-is for frontend compatibility
                    return segments

                # Legacy format: {warmup: {...}, main: {...}, cooldown: {...}}
                # Convert to new format for compatibility
                if isinstance(segments, dict) and (
                    "warmup" in segments or "main" in segments or "cooldown" in segments
                ):
                    steps = []

                    # Handle warmup
                    warmup = segments.get("warmup", {})
                    if warmup:
                        steps.append(
                            {
                                "name": "Warm-up",
                                "value": (
                                    warmup.get("distance", 0)
                                    if isinstance(warmup, dict)
                                    else 0
                                ),
                                "durationType": "DISTANCE",
                                "target": (
                                    warmup.get("target", {})
                                    if isinstance(warmup, dict)
                                    else {}
                                ),
                                "intensity": "EASY",
                            }
                        )

                    # Handle main
                    main = segments.get("main", {})
                    if main:
                        steps.append(
                            {
                                "name": "Main",
                                "value": (
                                    main.get("distance", 0)
                                    if isinstance(main, dict)
                                    else 0
                                ),
                                "durationType": "DISTANCE",
                                "target": (
                                    main.get("target", {})
                                    if isinstance(main, dict)
                                    else {}
                                ),
                                "intensity": "STEADY",
                            }
                        )

                    # Handle cooldown
                    cooldown = segments.get("cooldown", {})
                    if cooldown:
                        steps.append(
                            {
                                "name": "Cool-down",
                                "value": (
                                    cooldown.get("distance", 0)
                                    if isinstance(cooldown, dict)
                                    else 0
                                ),
                                "durationType": "DISTANCE",
                                "target": (
                                    cooldown.get("target", {})
                                    if isinstance(cooldown, dict)
                                    else {}
                                ),
                                "intensity": "EASY",
                            }
                        )

                    # Return in new format
                    return {
                        "steps": steps,
                        "units": "mi",
                        "targetType": "PACE",
                        "notes": segments.get("notes", ""),
                    }

                # If it's already an array or unknown format, return None
                return None
            except Exception as e:
                logger.warning(f"Failed to parse segments: {e}")
                return None

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
                            "race_name": plan.race_name,
                            "race_location": plan.race_location,
                            "race_metadata": plan.race_metadata,
                            "primary_goal": plan.primary_goal,
                            "target_time": plan.target_time,
                            "training_days": plan.training_days,
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


# ✅ POST /api/plan/create — create a new training plan
@plan_bp.route("/create", methods=["POST"])
@requires_auth
def create_plan_route():
    """Create a new training plan with GPT-generated workouts."""
    user_id = g.user_id

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        validated_data = PlanCreateSchema.model_validate(data)
        plan_dict = validated_data.model_dump()

        if str(plan_dict.get("primary_goal", "")).lower() == "target time":
            return (
                jsonify(
                    {
                        "error": "Target Time plans are under construction. Please choose 'Just Finish' to generate a plan."
                    }
                ),
                400,
            )

        user_timezone = resolve_timezone(plan_dict) or "UTC"
        plan_dict["user_timezone"] = user_timezone

        logger.info(f"Creating new training plan for user {user_id}")

        activity_weeks = int(data.get("activity_weeks", 12) or 12)

        with get_session() as session:
            result = run_v2_plan_generation(
                session=session,
                user_id=str(user_id),
                plan_request=plan_dict,
                activity_weeks=activity_weeks,
                mode="rolling",  # Only Week 1 gets details; weeks 2+ are basic workout types
            )

            if not result.get("valid") or not result.get("validated_plan"):
                violations = result.get("violations", [])
                logger.error(
                    "V2 plan generation failed validation for user %s: %s",
                    user_id,
                    violations,
                )
                return (
                    jsonify(
                        {
                            "error": "Generated plan failed validation.",
                            "violations": violations,
                        }
                    ),
                    400,
                )

            from src.services.training_plan.plan_storage_service import (
                PlanStorageService,
            )

            plan_storage = PlanStorageService()
            validation_payload = {
                "valid": True,
                "validated_plan": result["validated_plan"],
                "violations": result.get("violations", []),
            }
            plan_id = plan_storage.save_validated_plan(
                session=session,
                user_id=str(user_id),
                validated_plan=validation_payload,
                plan_request=plan_dict,
            )

        logger.info(f"Successfully created plan {plan_id}")

        return (
            jsonify(
                {
                    "status": "success",
                    "plan_id": plan_id,
                    "message": "Training plan created successfully",
                }
            ),
            201,
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        logger.error(f"Error creating plan: {e}", exc_info=True)
        return jsonify({"error": "Failed to create training plan"}), 500


# ✅ POST /api/plan/draft — generate a draft plan (no save)
@plan_bp.route("/draft", methods=["POST"])
@requires_auth
def create_plan_draft_route():
    """Generate a draft training plan without saving."""
    user_id = g.user_id

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        validated = PlanCreateSchema.model_validate(data)
        plan_request = validated.model_dump()

        if str(plan_request.get("primary_goal", "")).lower() == "target time":
            return (
                jsonify(
                    {
                        "error": "Target Time plans are under construction. Please choose 'Just Finish' to generate a draft."
                    }
                ),
                400,
            )

        user_timezone = resolve_timezone(plan_request) or "UTC"
        plan_request["user_timezone"] = user_timezone
        activity_weeks = int(data.get("activity_weeks", 12) or 12)

        with get_session() as session:
            result = run_v2_plan_generation(
                session=session,
                user_id=str(user_id),
                plan_request=plan_request,
                activity_weeks=activity_weeks,
                mode="rolling",  # Only Week 1 gets details; weeks 2+ are basic workout types
            )
            draft_payload = build_standard_draft_payload(
                validation_result=result, timezone=user_timezone
            )
            draft_payload["plan_request"] = plan_request

        return jsonify({"status": "success", "draft": draft_payload}), 200

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating draft plan: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate draft plan"}), 500


@plan_bp.route("/approve", methods=["POST"])
@requires_auth
def approve_plan_route():
    """Approve a previously generated draft and save it as active plan."""
    user_id = g.user_id

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        payload = request.get_json()
        if not payload:
            return jsonify({"error": "Request body is required"}), 400

        # Expect client to send back { validation: { validated_plan: ... }, plan_request }
        validation = payload.get("validation")
        plan_request = payload.get("plan_request")
        if not isinstance(validation, dict) or not isinstance(plan_request, dict):
            return jsonify({"error": "validation and plan_request are required"}), 400

        # Extract validated_plan from validation object (frontend sends validation.validated_plan)
        validated_plan = validation.get("validated_plan") or validation
        if not isinstance(validated_plan, dict):
            return (
                jsonify({"error": "validated_plan is required in validation object"}),
                400,
            )

        from src.services.training_plan.plan_storage_service import PlanStorageService

        with get_session() as session:
            # Use Layer 6 to save the validated plan
            plan_storage = PlanStorageService()
            plan_id = plan_storage.save_validated_plan(
                session=session,
                user_id=str(user_id),
                validated_plan=validated_plan,
                plan_request=plan_request,
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "plan_id": plan_id,
                    "message": "Plan approved and saved",
                }
            ),
            201,
        )

    except ValueError as e:
        logger.error(f"Approval validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error approving plan: {e}", exc_info=True)
        return jsonify({"error": "Failed to approve plan"}), 500


# ✅ POST /api/plan/<plan_id>/week/<week_num>/rebuild — rebuild week details with adjustments
@plan_bp.route("/<int:plan_id>/week/<int:week_num>/rebuild", methods=["POST"])
@requires_auth
def rebuild_week_route(plan_id, week_num):
    """
    Rebuild workout details for a specific week with pace adjustments.

    Request body (optional):
        {
            "previous_week_logs": [
                {
                    "run_type": "easy",
                    "planned_mi": 4.0,
                    "done_mi": 4.0,
                    "rpe": 3,
                    "avg_hr": 140  // optional
                },
                ...
            ]
        }

    If previous_week_logs not provided, attempts to fetch from database/Strava.
    """
    user_id = g.user_id

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        payload = request.get_json() or {}
        previous_week_logs_dict = payload.get("previous_week_logs")

        with get_session() as session:
            # Verify plan belongs to user
            from src.db.dao.plans_dao import get_plan

            plan = get_plan(session, plan_id)
            if not plan:
                return jsonify({"error": "Plan not found"}), 404

            if str(plan.user_id) != str(user_id):
                return jsonify({"error": "Unauthorized"}), 403

            # Fetch previous week logs if provided
            from src.services.training_plan.week_log_service import (
                convert_request_logs_to_week_logs,
                fetch_week_logs,
            )

            previous_week_logs = None
            if previous_week_logs_dict:
                previous_week_logs = convert_request_logs_to_week_logs(
                    previous_week_logs_dict
                )
            elif week_num > 1:
                # Try to fetch from database/Strava
                previous_week_logs = fetch_week_logs(
                    session=session,
                    plan_id=plan_id,
                    week_num=week_num - 1,
                    race_date=plan.race_date or date.today(),
                    request_logs=None,
                )

            # Rebuild week
            from src.services.training_plan.weekly_rebuild_service import (
                WeeklyRebuildService,
            )

            rebuild_service = WeeklyRebuildService()
            result = rebuild_service.rebuild_week(
                session=session,
                plan_id=plan_id,
                week_num=week_num,
                previous_week_logs=previous_week_logs,
                initial_seed=None,  # Will regenerate from plan
            )

            session.commit()

            logger.info(
                f"Successfully rebuilt week {week_num} for plan {plan_id} "
                f"(pace_adjusted={result.get('pace_adjusted', False)})"
            )

            return (
                jsonify(
                    {
                        "status": "success",
                        "week_number": week_num,
                        "message": f"Week {week_num} rebuilt successfully",
                        "week": result,
                    }
                ),
                200,
            )

    except ValueError as e:
        logger.error(f"Validation error rebuilding week: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error rebuilding week: {e}", exc_info=True)
        return jsonify({"error": "Failed to rebuild week"}), 500
