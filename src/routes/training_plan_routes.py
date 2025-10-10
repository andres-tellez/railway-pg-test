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


# ✅ /api/plan/readiness-assessment — Test endpoint for athlete readiness assessment
@training_plan_bp.route("/readiness-assessment", methods=["GET", "OPTIONS"])
def get_readiness_assessment():
    """
    Standalone endpoint to test the athlete readiness assessment module.
    This computes and logs the readiness metrics without generating a plan.

    For testing: Pass user_id as query param or header X-User-Id
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        print("🔍 CORS preflight request for readiness-assessment")
        return "", 200

    print("🏃 GET request to readiness-assessment endpoint")
    from src.services.athlete_readiness_assessment import assess_runner_readiness
    from src.services.training_plan_data_assembler import assemble_training_plan_data

    # Get user_id from query param, header, or g (if authenticated)
    user_id_str = request.args.get('user_id') or request.headers.get('X-User-Id') or getattr(g, 'user_id', None)
    print(f"🔍 Received user_id: {user_id_str}")
    print(f"🔍 Request headers: {dict(request.headers)}")

    if not user_id_str:
        print("❌ No user_id found")
        return jsonify({"error": "user_id required (query param or X-User-Id header)"}), 400

    try:
        user_id = uuid.UUID(str(user_id_str))
        print(f"✅ Valid user_id: {user_id}")
    except (ValueError, AttributeError):
        print(f"❌ Invalid user_id format: {user_id_str}")
        return jsonify({"error": "Invalid user_id format"}), 400

    with get_session() as session:
        try:
            # Load user data (same as plan generation)
            data_bundle = assemble_training_plan_data(session, user_id)

            user_profile = data_bundle.get('user_profile', {})
            race_date_str = user_profile.get('race_date')

            if not race_date_str:
                return jsonify({"error": "No race date set in user profile"}), 400

            # Parse race date
            if isinstance(race_date_str, str):
                race_date = datetime.strptime(race_date_str, '%Y-%m-%d').date()
            else:
                race_date = race_date_str

            # Run readiness assessment
            readiness = assess_runner_readiness(
                activities=data_bundle.get('activities', []),
                user_profile=user_profile,
                race_date=race_date
            )

            # Return the assessment
            return jsonify({
                "success": True,
                "readiness_assessment": readiness,
                "message": "Check server logs for detailed readiness assessment output"
            }), 200

        except Exception as e:
            print(f"❌ Error in readiness assessment: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


# ✅ /api/plan/training-profile — Test endpoint for training profile normalization
@training_plan_bp.route("/training-profile", methods=["GET", "OPTIONS"])
def get_training_profile():
    """
    Standalone endpoint to test the training profile normalization (Stage 2).
    This converts readiness assessment into Jack Daniels plan parameters.

    For testing: Pass user_id as query param or header X-User-Id
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        print("🔍 CORS preflight request for training-profile")
        return "", 200

    print("🏗️ GET request to training-profile endpoint")
    from src.services.athlete_readiness_assessment import assess_runner_readiness
    from src.services.training_profile_normalizer import normalize_training_profile
    from src.services.training_plan_data_assembler import assemble_training_plan_data

    # Get user_id from query param, header, or g (if authenticated)
    user_id_str = request.args.get('user_id') or request.headers.get('X-User-Id') or getattr(g, 'user_id', None)
    print(f"🔍 Received user_id: {user_id_str}")

    if not user_id_str:
        print("❌ No user_id found")
        return jsonify({"error": "user_id required (query param or X-User-Id header)"}), 400

    try:
        user_id = uuid.UUID(str(user_id_str))
        print(f"✅ Valid user_id: {user_id}")
    except (ValueError, AttributeError):
        print(f"❌ Invalid user_id format: {user_id_str}")
        return jsonify({"error": "Invalid user_id format"}), 400

    with get_session() as session:
        try:
            # Load user data (same as plan generation)
            data_bundle = assemble_training_plan_data(session, user_id)

            user_profile = data_bundle.get('user_profile', {})
            race_date_str = user_profile.get('race_date')

            if not race_date_str:
                return jsonify({"error": "No race date set in user profile"}), 400

            # Parse race date
            if isinstance(race_date_str, str):
                race_date = datetime.strptime(race_date_str, '%Y-%m-%d').date()
            else:
                race_date = race_date_str

            # Stage 1: Run readiness assessment
            readiness_result = assess_runner_readiness(
                activities=data_bundle.get('activities', []),
                user_profile=user_profile,
                race_date=race_date
            )

            # Stage 2: Normalize training profile
            training_profile = normalize_training_profile(
                readiness=readiness_result.get('summary', readiness_result),
                user_profile=user_profile
            )

            # Return both stages
            return jsonify({
                "success": True,
                "stage1_readiness": readiness_result,
                "stage2_training_profile": training_profile,
                "message": "Check server logs for detailed Stage 1 & 2 output"
            }), 200

        except Exception as e:
            print(f"❌ Error in training profile normalization: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


# ✅ /api/plan/four-stage-plan — Generate and save complete plan using 4-stage system
@training_plan_bp.route("/four-stage-plan", methods=["POST", "OPTIONS"])
def generate_four_stage_plan():
    """
    Generate and save a complete training plan using the 4-stage system.
    This creates a new plan in the database and returns the plan ID.
    """
    if request.method == "OPTIONS":
        print("🔍 CORS preflight for four-stage-plan")
        return "", 200

    print("🚀 POST /four-stage-plan called")

    from src.services.four_stage_plan_generator import generate_and_save_four_stage_plan

    # --- Get user ID ---
    user_id_str = (
        request.args.get("user_id")
        or request.headers.get("X-User-Id")
        or getattr(g, "user_id", None)
    )
    if not user_id_str:
        return jsonify({"error": "user_id required"}), 400

    try:
        user_id = uuid.UUID(str(user_id_str))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid user_id format"}), 400

    # --- Get race info from request body ---
    data = request.get_json() or {}
    race_date_str = data.get("race_date")
    race_distance = data.get("race_distance", "Marathon")

    if not race_date_str:
        return jsonify({"error": "race_date required in request body"}), 400

    try:
        race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid race_date format. Use YYYY-MM-DD"}), 400

    with get_session() as session:
        try:
            # Generate and save the complete plan
            result = generate_and_save_four_stage_plan(
                session=session,
                user_id=user_id,
                race_date=race_date,
                race_distance=race_distance
            )

            if result["success"]:
                return jsonify(result), 200
            else:
                return jsonify({"error": result["error"]}), 500

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


# ✅ /api/plan/structured-plan — Test endpoint for structured plan generation (Stage 3)
@training_plan_bp.route("/structured-plan", methods=["GET", "OPTIONS"])
def get_structured_plan():
    """
    Standalone endpoint to test the structured plan generation (Stage 3).
    This creates a week-by-week training plan using Stage 1 & 2 results.

    For testing: Pass user_id as query param or header X-User-Id
    """
    # Handle CORS preflight
    if request.method == "OPTIONS":
        print("🔍 CORS preflight request for structured-plan")
        return "", 200

    print("🏗️ GET request to structured-plan endpoint")
    from src.services.athlete_readiness_assessment import assess_runner_readiness
    from src.services.training_profile_normalizer import normalize_training_profile
    from src.services.training_plan_builder import build_training_plan
    from src.services.training_plan_data_assembler import assemble_training_plan_data

    # Get user_id from query param, header, or g (if authenticated)
    user_id_str = request.args.get('user_id') or request.headers.get('X-User-Id') or getattr(g, 'user_id', None)
    print(f"🔍 Received user_id: {user_id_str}")

    if not user_id_str:
        print("❌ No user_id found")
        return jsonify({"error": "user_id required (query param or X-User-Id header)"}), 400

    try:
        user_id = uuid.UUID(str(user_id_str))
        print(f"✅ Valid user_id: {user_id}")
    except (ValueError, AttributeError):
        print(f"❌ Invalid user_id format: {user_id_str}")
        return jsonify({"error": "Invalid user_id format"}), 400

    with get_session() as session:
        try:
            # Load user data (same as plan generation)
            data_bundle = assemble_training_plan_data(session, user_id)

            user_profile = data_bundle.get('user_profile', {})
            race_date_str = user_profile.get('race_date')

            if not race_date_str:
                return jsonify({"error": "No race date set in user profile"}), 400

            # Parse race date
            if isinstance(race_date_str, str):
                race_date = datetime.strptime(race_date_str, '%Y-%m-%d').date()
            else:
                race_date = race_date_str

            # Stage 1: Run readiness assessment
            readiness_result = assess_runner_readiness(
                activities=data_bundle.get('activities', []),
                user_profile=user_profile,
                race_date=race_date
            )

            # Stage 2: Normalize training profile
            training_profile = normalize_training_profile(
                readiness=readiness_result.get('summary', readiness_result),
                user_profile=user_profile
            )

            # Stage 3: Build structured plan
            start_date = datetime.today().date()
            training_days = [str(day) for day in user_profile.get('training_days', ['MON', 'WED', 'FRI', 'SAT'])]

            # Standard heart rate zones
            zones = {
                "easy": "Z1-2",
                "thresh": "Z3",
                "marathon": "Z3",
                "vo2": "Z4",
                "rep": "Z4-5"
            }

            structured_plan = build_training_plan(
                normalized=training_profile,
                start_date=start_date,
                race_date=race_date,
                training_days=training_days,
                zones=zones
            )

            # Stage 4: Add pace and HR zone mapping
            from src.services.pace_zone_mapper import map_pace_zones, estimate_vdot_from_race_time

            # Estimate VDOT if not available
            if not user_profile.get('vdot'):
                # Try to estimate from past race times or use default
                past_races = user_profile.get('past_races', [])
                if past_races:
                    # Use most recent race for VDOT estimation
                    user_profile['vdot'] = estimate_vdot_from_race_time("marathon", "4:00:00")  # placeholder
                else:
                    user_profile['vdot'] = 45  # default

            # Add max HR if not available
            if not user_profile.get('max_hr'):
                user_profile['max_hr'] = 220 - user_profile.get('age', 35)

            # Map paces and zones to the structured plan
            enriched_plan = map_pace_zones(structured_plan["weeks"], user_profile)
            structured_plan["weeks"] = enriched_plan

            # Return all four stages
            return jsonify({
                "success": True,
                "stage1_readiness": readiness_result,
                "stage2_training_profile": training_profile,
                "stage3_4_structured_plan": structured_plan,
                "message": "Check server logs for detailed Stage 1, 2, 3 & 4 output"
            }), 200

        except Exception as e:
            print(f"❌ Error in structured plan generation: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500


@training_plan_bp.route("/gpt-plan-generation", methods=["POST"])
@requires_auth
def get_gpt_plan_generation():
    """
    GPT-based complete training plan generation using normalized profile
    Saves the plan to database and returns plan_id for display in the plan table
    """
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            return jsonify({"error": "user_id required (X-User-Id header)"}), 400

        # Get race details from request body
        data = request.get_json() or {}
        race_date = data.get('race_date', '2025-12-07')
        race_distance = data.get('race_distance', 'Marathon')

        print(f"\n📅 GPT Plan Generation request for user: {user_id}")
        print(f"  • Race Date: {race_date}")
        print(f"  • Race Distance: {race_distance}")

        # Hardcoded prompt for now (as requested)
        prompt = """You are an expert marathon coach applying the Jack Daniels methodology.

CRITICAL: Generate EXACTLY 8 weeks of training data in a valid JSON array (no commentary).

### BASE INPUT (from Step 2)
{
  "base_mileage": 15.6,
  "phase": "Quality-Phase",
  "target_weekly_mileage": 35.0,
  "ramp_limit_pct": 0.05,
  "long_run_cap": 12.3,
  "threshold_sessions_per_week": 1,
  "easy_run_ratio": 0.75,
  "recommended_training_days": 4,
  "recovery_week_frequency": 3
}

Timeline:
- Start Date: 2025-10-08
- Race Date: 2025-12-07
- Race Type: Marathon (26.2 mi)
- Training Days: MON, WED, THU, SAT

Return ONLY this structure:

[
  {
    "week_number": 1,
    "phase": "Quality-Phase" | "Race-Specific" | "Taper",
    "total_miles": number,
    "week_start": "YYYY-MM-DD",
    "long_run_mi": number,
    "threshold_runs": number,
    "easy_runs": number,
    "workouts": [
      {
        "date": "YYYY-MM-DD",
        "workout_type": "Easy" | "Threshold" | "Long" | "Recovery" | "Race",
        "distance_mi": number,
        "target_zone": "Z1-2" | "Z2-3" | "Z3-4",
        "description": "short summary"
      }
    ]
  }
]

---

### RULES

1️⃣ **Mileage Progression**
- Start = base_mileage (15–16 mi).
- Ramp ≤ 5 % / week (±1 mi tolerance).
- Recovery week every 3 weeks (-20 %).
- Peak ≤ target_weekly_mileage (≈ 35 mi).
- Taper = 80 % → 60 % → 40 % of peak.

2️⃣ **Long Runs**
- 1 × per week (SAT).
- 25–30 % of weekly mileage, rounded to nearest 0.5 mi.
- Zone = Z2-3.
- Cap = long_run_cap (12 mi).
- Long run must be largest run of week.

3️⃣ **Threshold Runs**
- Exactly 1 × per week (WED).
- 8–12 % of weekly mileage (3–5 mi typical).
- Zone = Z3-4.
- Never day before or after Long run.

4️⃣ **Easy Runs**
- Fill remaining mileage.
- Each Easy run 5–7 mi.
- Zone = Z1-2.
- Two Easy days per week (MON & THU).

5️⃣ **Phases**
- Weeks 1–3 = Quality-Phase
- Weeks 4–6 = Race-Specific
- Weeks 7–8 = Taper
- Week 8 includes Race Day (26.2 mi Z3-4).

6️⃣ **Safety and Consistency**
- Long-run ratio ≤ 0.35 of weekly.
- No week-to-week drop > 20 % except taper.
- All distances end in .0 or .5 mi (no decimals).

7️⃣ **Validation Checks**
- Sum(workouts) ≈ total_miles ± 1 mi.
- Each week's long run ≥ any Easy run.
- Threshold run ≈ 8–12 % of week total.

---

CRITICAL: Produce exactly 8 weeks of valid JSON matching all rules.
If the output risks truncation, return weeks 1–4 first, then weeks 5–8."""

        print("🤖 Calling GPT for plan generation...")

        # Call GPT with the prompt
        response = get_gpt_response(prompt, require_json=True)

        if not response:
            return jsonify({"error": "GPT returned no response"}), 500

        # Parse the JSON response from GPT
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse GPT JSON response: {e}")
            print(f"Raw response: {response}")
            return jsonify({"error": "Failed to parse GPT response"}), 500

        print(f"✅ GPT plan generation complete")
        print(f"📊 Response: {parsed_response}")

        # Convert GPT response to database format and save
        try:
            # Import the four-stage generator to use its database saving logic
            from src.services.four_stage_plan_generator import convert_gpt_response_to_database_format, save_plan_to_database

            # Convert GPT single week response to multiple weeks for database
            database_workouts = convert_gpt_response_to_database_format(parsed_response, race_date, race_distance)

            # Save to database
            plan_id = save_plan_to_database(
                user_id=user_id,
                race_date=race_date,
                race_distance=race_distance,
                workouts=database_workouts,
                plan_name=f"GPT Generated Plan - {race_distance}",
                plan_description="Training plan generated by GPT using Jack Daniels methodology"
            )

            print(f"✅ GPT plan saved to database with ID: {plan_id}")

            return jsonify({
                "success": True,
                "plan_id": plan_id,
                "plan_name": f"GPT Generated Plan - {race_distance}",
                "race_date": race_date,
                "race_distance": race_distance,
                "message": "GPT training plan generated and saved successfully!"
            })

        except Exception as db_error:
            print(f"❌ Error saving GPT plan to database: {str(db_error)}")
            # Return the plan data anyway for display
            return jsonify({
                "success": True,
                "training_plan": parsed_response,
                "user_id": user_id,
                "error": f"Plan generated but failed to save to database: {str(db_error)}"
            })

    except Exception as e:
        print(f"❌ Error in plan generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@training_plan_bp.route("/gpt-profile-normalization", methods=["GET"])
@requires_auth
def get_gpt_profile_normalization():
    """
    GPT-based training profile normalization using fitness assessment results
    """
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            return jsonify({"error": "user_id required (X-User-Id header)"}), 400

        print(f"\n📊 GPT Profile Normalization request for user: {user_id}")

        # Hardcoded prompt for now (as requested)
        prompt = """You are a certified running coach and exercise physiologist specializing in the Jack Daniels methodology.

Using the runner's readiness assessment (below), normalize the training profile into safe, progressive parameters for marathon plan generation.

Return ONLY a JSON object structured like this:

{
  "phase": "Base-Build" | "Quality-Phase" | "Race-Specific",
  "target_weekly_mileage": number,
  "ramp_limit_pct": number,
  "long_run_cap": number,
  "threshold_sessions_per_week": number,
  "easy_run_ratio": number,
  "recommended_training_days": number,
  "mileage_multiplier": number,
  "max_weekly_increase": number,
  "min_weekly_mileage": number,
  "max_weekly_mileage": number,
  "recovery_week_frequency": number,
  "vdot_adjustment": number,
  "notes": "1-2 sentence summary of how these limits should shape the plan"
}

### NORMALIZATION RULES
1. Category-based templates:
   - **Low-Base** → ramp ≤ 5 %; mileage × 1.8; long run ≤ 18 mi; 1 threshold session; easy ratio = 0.75; phase = Base-Build.
   - **Stable-Base** → ramp ≤ 8 %; mileage × 2.2; long run ≤ 22 mi; 2 threshold sessions; easy ratio = 0.70; phase = Quality-Phase.
   - **High-Base** → ramp ≤ 10 %; mileage × 2.6; long run ≤ 24 mi; 3 threshold sessions; easy ratio = 0.65; phase = Race-Specific.

2. Derived calculations:
   - `target_weekly_mileage = base_mileage × mileage_multiplier`
   - `long_run_cap = min(long_run_cap_template, target_weekly_mileage × 0.35)`
   - `max_weekly_increase = target_weekly_mileage × ramp_limit_pct`
   - Adjust ramp limit and threshold sessions down 1 level if age > 45 (age_factor < 1.0).

3. Timeline adjustment:
   - If weeks_to_race < 8 → reduce target mileage × 0.8
   - If weeks_to_race > 20 → increase target mileage × 1.1

4. Safe bounds:
   - `min_weekly_mileage = base_mileage × 0.8`
   - `max_weekly_mileage = target_weekly_mileage × 1.2`
   - Recovery week every 3–4 weeks (depending on category).

5. Output must keep values rounded to one decimal and percentages as decimals (e.g., 0.05 for 5 %).

---

### INPUT (from Step 1)
{
  "vdot_estimate": 51,
  "category": "Stable-Base",
  "readiness_index": 62,
  "derived_metrics": {
      "avg_weekly_mileage": 20,
      "longest_run_mi": 13.9,
      "weeks_with_3plus_runs": 5,
      "total_weeks": 6,
      "consistency_score": 83,
      "hr_distribution": {"Z1_2": 56, "Z3": 34, "Z4": 10}
  },
  "summary": "Runner shows solid aerobic base and consistent training. Suitable for moderate ramp-up (≤ 6%) toward marathon readiness."
}

Additional context:
- Age: 50
- Race date: 2025-12-06
- Start date: 2025-10-08

Analyze this data and return ONLY the JSON object with normalized training parameters."""

        print("🤖 Calling GPT for profile normalization...")

        # Call GPT with the prompt
        response = get_gpt_response(prompt, require_json=True)

        if not response:
            return jsonify({"error": "GPT returned no response"}), 500

        # Parse the JSON response from GPT
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse GPT JSON response: {e}")
            print(f"Raw response: {response}")
            return jsonify({"error": "Failed to parse GPT response"}), 500

        print(f"✅ GPT profile normalization complete")
        print(f"📊 Response: {parsed_response}")

        return jsonify({
            "success": True,
            "normalized_profile": parsed_response,
            "user_id": user_id
        })

    except Exception as e:
        print(f"❌ Error in profile normalization: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@training_plan_bp.route("/vdot-estimation", methods=["GET"])
@requires_auth
def get_vdot_estimation():
    """
    GPT-based VDOT estimation using recent running data and Jack Daniels methodology
    """
    try:
        user_id = request.headers.get('X-User-Id')
        if not user_id:
            return jsonify({"error": "user_id required (X-User-Id header)"}), 400

        print(f"\n🏃 GPT VDOT Estimation request for user: {user_id}")

        # Hardcoded prompt for now (as requested)
        prompt = """You are a certified running coach using Jack Daniels methodology.

Analyze the runner's recent data to estimate:
- VDOT (fitness)
- Consistency Score (training regularity)
- Readiness Index (0–100)
- Base Category (Low-Base, Stable-Base, or High-Base)

Return ONLY a JSON object like this:
{
  "vdot_estimate": number,
  "category": "Low-Base" | "Stable-Base" | "High-Base",
  "readiness_index": number,
  "derived_metrics": {
      "avg_weekly_mileage": number,
      "longest_run_mi": number,
      "weeks_with_3plus_runs": number,
      "total_weeks": number,
      "consistency_score": number,
      "hr_distribution": {"Z1_2": number, "Z3": number, "Z4": number}
  },
  "summary": "1-2 sentence summary of fitness level and next-step recommendation"
}

Rules for GPT to follow:
1. Estimate VDOT using Jack Daniels pace–VDOT equivalence (pace & HR).
2. Base mileage = average of recent weekly totals.
3. Consistency score = (weeks ≥ 3 runs / total weeks) × 100 %.
4. Readiness Index = (0.35 × Base Mileage / 35 × 100) + (0.25 × Consistency Score) + (0.25 × HR Balance Score) + (0.15 × Longest Run Ratio × 100) × Age Factor (0.95 if age 45–54).
5. Category:
   - Low-Base < 25 mi/week or Inconsistent
   - Stable-Base 25–40 mi/week & consistent
   - High-Base > 40 mi/week or VDOT ≥ 55

Runner Profile:
- Age: 50
- Weight: 171 lbs
- Height: 5 ft 10 in
- Goal: Lose Weight
- Past Races: Marathon
- Longest Run: 26 mi
- Max HR: 177 bpm
- Current Base Mileage: 20 mi/week

Recent Runs (Date | Distance | Avg Pace | HR Zone):
2025-10-08 | 4.0 mi @ 6:49/mi (157 bpm, Z3)
2025-10-07 | 6.8 mi @ 6:11/mi (152 bpm, Z3)
2025-10-04 | 10.0 mi @ 5:49/mi (132 bpm, Z2)
2025-09-30 | 6.3 mi @ 6:24/mi (149 bpm, Z3)
2025-09-27 | 10.0 mi @ 6:19/mi (143 bpm, Z3)
2025-09-25 | 6.8 mi @ 6:21/mi (155 bpm, Z3)
2025-09-22 | 5.1 mi @ 6:28/mi (154 bpm, Z3)
2025-09-20 | 13.9 mi @ 5:41/mi (140 bpm, Z2)

Recent Weekly Mileage and Zones:
Oct 06 | 10.8 mi @ 6:30/mi (mixed)
Sep 29 | 16.3 mi @ 6:07/mi (mostly Z2)
Sep 22 | 21.9 mi @ 6:23/mi (mostly Z2)
Sep 15 | 19.9 mi @ 5:40/mi (mostly Z2)
Sep 08 | 10.7 mi @ 6:15/mi (mostly Z2)
Sep 01 | 26.5 mi @ 6:06/mi (mostly Z2)

Analyze this data and return ONLY the JSON object."""

        print("🤖 Calling GPT for VDOT estimation...")

        # Call GPT with the prompt
        response = get_gpt_response(prompt, require_json=True)

        if not response:
            return jsonify({"error": "GPT returned no response"}), 500

        # Parse the JSON response from GPT
        try:
            parsed_response = json.loads(response)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse GPT JSON response: {e}")
            print(f"Raw response: {response}")
            return jsonify({"error": "Failed to parse GPT response"}), 500

        print(f"✅ GPT VDOT estimation complete")
        print(f"📊 Response: {parsed_response}")

        return jsonify({
            "success": True,
            "vdot_estimation": parsed_response,
            "user_id": user_id
        })

    except Exception as e:
        print(f"❌ Error in VDOT estimation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# Removed unused debug and legacy assessment endpoints - not used by frontend
