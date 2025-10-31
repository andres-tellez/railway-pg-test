# src/routes/plan_routes.py

from flask import Blueprint, jsonify, g, request
from sqlalchemy.orm import joinedload
import uuid
import logging

from src.db.db_session import get_session
import os
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
from src.services.training_plan.orchestrator_three_pass import ThreePassOrchestrator
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from datetime import datetime, date
from src.services.training_plan.pass1_weeks_selector import Pass1WeeksSelector
from src.services.training_plan.weekly_total_calculator import (
    calculate_weekly_totals_from_long_runs,
)
from src.services.training_plan.pass3_workout_distribution import (
    Pass3WorkoutDistribution,
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
                            "race_name": plan.race_name,
                            "race_location": plan.race_location,
                            "primary_goal": plan.primary_goal,
                            "marathon_experience": plan.marathon_experience,
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
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        # Validate with Pydantic schema
        validated_data = PlanCreateSchema.model_validate(data)
        plan_dict = validated_data.model_dump()

        logger.info(f"Creating new training plan for user {user_id}")
        logger.debug(f"Plan data: {plan_dict}")

        # Create plan using deterministic LR-first path (unconditional)
        with get_session() as session:
            # Run three-pass and save immediately
            dc = DataCollectionService()
            ic = InsightsCalculationService()
            raw = dc.collect_all_data(
                session=session,
                user_id=str(user_id),
                plan_request=plan_dict,
                activity_weeks=12,
            )
            insights = ic.calculate_all_insights(raw)

            # Use Pass 1 to compute weeks
            p1_selector = Pass1WeeksSelector()
            p1 = p1_selector.select_weeks(
                session=session,
                user_id=str(user_id),
                plan_request=plan_dict,
            )
            recom_weeks = int(p1.get("weeks", 16))

            ctx = {
                "session": session,
                "user_id": str(user_id),
                "plan_request": plan_dict,
                "weeks": recom_weeks,
                "current_weekly_mileage": insights.get("current_fitness", {}).get(
                    "weekly_mileage", 0
                ),
                "longest_recent_run": insights.get("current_fitness", {}).get(
                    "longest_run", 0
                ),
                "experience": (plan_dict.get("marathon_experience") or "").lower(),
                "training_days": plan_dict.get("training_days")
                or ["Mon", "Wed", "Thu", "Sat"],
            }
            from src.services.training_plan.plan_storage_service import (
                PlanStorageService,
            )
            from src.services.training_plan.plan_validation_service import (
                PlanValidationService,
            )

            tp = ThreePassOrchestrator()
            result = tp.generate_longrun_first(ctx)
            if not result.get("valid"):
                raise ValueError("Generated plan failed validation in three-pass mode")
            validation = {
                "valid": True,
                "validated_plan": result["validated_plan"],
                "violations": [],
            }
            plan_storage = PlanStorageService()
            plan_id = plan_storage.save_validated_plan(
                session=session,
                user_id=str(user_id),
                validated_plan=validation,
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

        # Validate basic required fields via existing schema
        validated = PlanCreateSchema.model_validate(data)
        plan_request = validated.model_dump()

        with get_session() as session:
            # L1 + L2 to build minimal context
            dc = DataCollectionService()
            ic = InsightsCalculationService()
            raw = dc.collect_all_data(
                session=session,
                user_id=str(user_id),
                plan_request=plan_request,
                activity_weeks=12,
            )
            insights = ic.calculate_all_insights(raw)

            use_longrun_first = True

            # Use Pass1WeeksSelector to compute recommended weeks
            p1_selector = Pass1WeeksSelector()
            p1 = p1_selector.select_weeks(
                session=session,
                user_id=str(user_id),
                plan_request=plan_request,
            )
            recom_weeks = int(p1.get("weeks", 16))

            ctx = {
                "session": session,
                "user_id": str(user_id),
                "plan_request": plan_request,
                "weeks": recom_weeks,
                "current_weekly_mileage": insights.get("current_fitness", {}).get(
                    "weekly_mileage", 0
                ),
                "longest_recent_run": insights.get("current_fitness", {}).get(
                    "longest_run", 0
                ),
                "experience": (plan_request.get("marathon_experience") or "").lower(),
                "training_days": plan_request.get("training_days")
                or ["Mon", "Wed", "Thu", "Sat"],
            }

            tp = ThreePassOrchestrator()
            # LR-only draft with correctness validation surfaced to UI
            from src.services.training_plan.pass1_longrun_first import (
                Pass1LongRunFirst,
            )

            lr_first = Pass1LongRunFirst()
            lr_out = lr_first.build(
                session=session,
                user_id=str(user_id),
                plan_request=plan_request,
            )

            # Compute simple validation for Week 1 against recent_3w_longest
            def _round_half(x: float) -> float:
                return round(x * 2) / 2.0

            recent_3w = lr_first._recent_longest_run_last_days(raw.get("strava_activities", []), days=21)  # type: ignore[attr-defined]

            # Calculate weekly totals from long runs (NEW: uses finisher-friendly calculator)
            training_days = plan_request.get("training_days") or [
                "Mon",
                "Wed",
                "Thu",
                "Sat",
            ]
            runs_per_week = len(training_days) if training_days else 4
            weeks_with_totals = calculate_weekly_totals_from_long_runs(
                weeks=lr_out.get("weeks", []),
                runs_per_week=runs_per_week,
            )
            if True:
                # Generate workout distributions using Pass3 (NEW: distributes remaining days)
                pass3 = Pass3WorkoutDistribution()
                pass3_result = pass3.run(weeks_with_totals, training_days)
                weeks_with_workouts = pass3_result.get("weeks", [])

                # Build final weeks structure with all fields
                weeks_simple = [
                    {
                        "week_number": w.get("week_number"),
                        "phase": w.get("phase", ""),
                        "long_run_miles": w.get("long_run_miles"),
                        "weekly_mileage": w.get("weekly_mileage", 0),
                        "workouts": w.get(
                            "workouts", []
                        ),  # Include workout distributions
                    }
                    for w in weeks_with_workouts
                ]
                violations = []
                if recent_3w and recent_3w > 0 and weeks_simple:
                    expected_w1 = _round_half(recent_3w + 1.0)
                    got_w1 = float(weeks_simple[0]["long_run_miles"] or 0)
                    if abs(got_w1 - expected_w1) > 1e-6:
                        violations.append(
                            {
                                "code": "WEEK1_MISMATCH",
                                "rule": "Week 1 baseline",
                                "details": f"Week 1 long run {got_w1:.1f} ≠ recent_3w_longest+1 ({expected_w1:.1f}).",
                                "suggestion": "Set Week 1 to last 3-week max + 1 mile (rounded to 0.5).",
                                "severity": "error",
                                "week": 1,
                            }
                        )
                if not recent_3w or recent_3w <= 0:
                    violations.append(
                        {
                            "code": "INSUFFICIENT_RECENT_DATA",
                            "rule": "Recent data missing",
                            "details": "No long run detected in the last 21 days to set Week 1 baseline.",
                            "suggestion": "Log a recent long run or start conservatively (8–12 mi) and rebuild.",
                            "week": 1,
                            "severity": "warning",
                        }
                    )

                # Sustained high-mileage long runs: warn if >=5 of any 6-week window are 19-20 miles
                lr_series = [
                    float(w.get("long_run_miles") or 0.0) for w in weeks_simple
                ]
                window = 6
                threshold = 19.0
                for start_idx in range(0, max(0, len(lr_series) - window + 1)):
                    segment = lr_series[start_idx : start_idx + window]
                    high_count = sum(1 for x in segment if x >= threshold)
                    if high_count >= 5:
                        violations.append(
                            {
                                "code": "SUSTAINED_HIGH_LONG_RUNS",
                                "rule": "Sustained peak long runs",
                                "details": f"{high_count}/{window} consecutive weeks at ≥{threshold:.0f} miles increases injury/overtraining risk.",
                                "suggestion": "Insert a cutback (−25% LR) and cap post‑peak weeks at 19 before taper.",
                                "week": start_idx + 1,
                                "severity": "error",
                            }
                        )
                        break

                # Taper quality checks
                if lr_series:
                    peak_val = max(lr_series)
                    peak_idx = lr_series.index(peak_val)
                    # 1) Taper must be non-increasing after peak
                    post_peak = lr_series[peak_idx + 1 :]
                    for i in range(1, len(post_peak)):
                        if post_peak[i] > post_peak[i - 1] + 1e-6:
                            violations.append(
                                {
                                    "code": "NON_MONOTONIC_TAPER",
                                    "rule": "Taper progression",
                                    "details": f"Long runs increase after peak (week {peak_idx+1}). Week {peak_idx+1+i} {post_peak[i-1]:.0f} → Week {peak_idx+2+i} {post_peak[i]:.0f}.",
                                    "suggestion": "Ensure each post‑peak week is ≤ previous week.",
                                    "week": peak_idx + 2 + i,
                                    "severity": "error",
                                }
                            )
                            break

                    # 2) Last 3 weeks should approximate 70/50/25% of peak (±1 mile tolerance)
                    if len(lr_series) >= 3:
                        last3 = lr_series[-3:]
                        targets = [
                            0.70 * peak_val,
                            0.50 * peak_val,
                            0.25 * peak_val,
                        ]
                        ok = all(abs(last3[i] - targets[i]) <= 1.0 for i in range(3))
                        if not ok:
                            violations.append(
                                {
                                    "code": "SUBOPTIMAL_TAPER_PATTERN",
                                    "rule": "3‑week taper targets",
                                    "details": f"Final weeks {last3} do not follow ≈[70%,50%,25%] of peak {peak_val:.0f}.",
                                    "suggestion": "Aim for ~14, 10, 5 after a 20‑mile peak (±1 mile tolerance).",
                                    "week": len(lr_series) - 2,
                                    "severity": "warning",
                                }
                            )

                    # 3) High long runs too close to race (≥18 within last 5 weeks excluding taper block)
                    last5_idx = max(0, len(lr_series) - 5)
                    last5 = lr_series[last5_idx:]
                    # Exclude final 3 taper weeks from this check
                    pre_taper_block = last5[:-3] if len(last5) > 3 else []
                    if any(x >= 18.0 for x in pre_taper_block):
                        violations.append(
                            {
                                "code": "HIGH_LR_TOO_CLOSE",
                                "rule": "High LR near race",
                                "details": "Detected ≥18‑mile long run within the last 5 weeks before race (outside taper).",
                                "suggestion": "Move remaining ≥18‑mile long runs earlier or reduce to ≤16 before taper.",
                                "week": last5_idx + 1,
                                "severity": "warning",
                            }
                        )

                # Check if plan duration fits before race date (post-generation validation)
                plan_duration_weeks = len(weeks_simple)
                race_date = plan_request.get("race_date")
                time_warning = None
                stretched_metadata = None
                start_date = None

                if race_date:
                    try:
                        from datetime import datetime, date, timedelta

                        if isinstance(race_date, str):
                            rd = datetime.fromisoformat(race_date.split("T")[0]).date()
                        elif isinstance(race_date, date):
                            rd = race_date
                        else:
                            rd = None

                        if rd:
                            today = date.today()

                            # Calculate start date (next Monday or closest Monday)
                            days_until_monday = (7 - today.weekday()) % 7
                            if days_until_monday == 0:
                                days_until_monday = 7
                            start_date = today + timedelta(days=days_until_monday)

                            weeks_available = (rd - start_date).days / 7.0
                            weeks_needed = plan_duration_weeks

                            # Apply recovery week insertion if plan is shorter than available weeks
                            recovery_metadata = None
                            # Calculate extra weeks (how many recovery weeks to insert)
                            extra_weeks_calc = int(weeks_available - weeks_needed)

                            if extra_weeks_calc > 0:
                                logger.info(
                                    f"Plan has {weeks_needed} weeks but {weeks_available:.1f} weeks available. Inserting {extra_weeks_calc} recovery weeks."
                                )

                            if weeks_needed < weeks_available:
                                from src.services.training_plan.recovery_week_insertion_service import (
                                    apply_recovery_week_insertion_if_needed,
                                )

                                weeks_with_recovery, recovery_metadata = (
                                    apply_recovery_week_insertion_if_needed(
                                        weeks_simple, race_date, start_date
                                    )
                                )

                                if recovery_metadata.get("inserted"):
                                    # Replace weeks_simple with version that includes recovery weeks
                                    weeks_simple = weeks_with_recovery

                                    # Recalculate workouts for ALL recovery weeks using Pass3
                                    # This ensures proper progression (Mon < Wed < Thu) for recovery weeks
                                    recovery_week_indices = [
                                        i
                                        for i, w in enumerate(weeks_simple)
                                        if w.get("phase") == "Recovery"
                                    ]

                                    if recovery_week_indices:
                                        # Recalculate workouts for all recovery weeks
                                        pass3 = Pass3WorkoutDistribution()
                                        for idx in recovery_week_indices:
                                            recovery_week = weeks_simple[idx]
                                            # Use Pass3 to generate workouts for recovery week with proper progression
                                            recovery_week_input = [
                                                {
                                                    "week_number": recovery_week[
                                                        "week_number"
                                                    ],
                                                    "phase": recovery_week["phase"],
                                                    "long_run_miles": recovery_week[
                                                        "long_run_miles"
                                                    ],
                                                    "weekly_mileage": recovery_week[
                                                        "weekly_mileage"
                                                    ],
                                                }
                                            ]
                                            pass3_result = pass3.run(
                                                recovery_week_input, training_days
                                            )
                                            if pass3_result.get(
                                                "weeks"
                                            ) and pass3_result["weeks"][0].get(
                                                "workouts"
                                            ):
                                                weeks_simple[idx]["workouts"] = (
                                                    pass3_result["weeks"][0]["workouts"]
                                                )

                                                # Verify progression: Mon < Wed < Thu
                                                workouts = weeks_simple[idx]["workouts"]
                                                mon_miles = next(
                                                    (
                                                        w.get("distance_miles", 0)
                                                        for w in workouts
                                                        if w.get("day") == "Mon"
                                                    ),
                                                    0,
                                                )
                                                wed_miles = next(
                                                    (
                                                        w.get("distance_miles", 0)
                                                        for w in workouts
                                                        if w.get("day") == "Wed"
                                                    ),
                                                    0,
                                                )
                                                thu_miles = next(
                                                    (
                                                        w.get("distance_miles", 0)
                                                        for w in workouts
                                                        if w.get("day") == "Thu"
                                                    ),
                                                    0,
                                                )

                                                if not (
                                                    mon_miles < wed_miles < thu_miles
                                                ):
                                                    logger.warning(
                                                        f"Recovery week {idx+1} does not have strict progression: Mon={mon_miles}, Wed={wed_miles}, Thu={thu_miles}"
                                                    )

                                    plan_duration_weeks = len(weeks_simple)
                                    weeks_needed = plan_duration_weeks

                            # Recalculate time assessment with updated weeks
                            buffer_weeks = weeks_available - weeks_needed
                            if weeks_available < weeks_needed:
                                # Not enough time
                                shortfall_weeks = weeks_needed - weeks_available
                                time_warning = {
                                    "code": "INSUFFICIENT_TIME",
                                    "type": "warning",
                                    "message": f"This plan requires {weeks_needed} weeks, but only {weeks_available:.1f} weeks are available before the race ({rd.strftime('%Y-%m-%d')}). You are {shortfall_weeks:.1f} weeks short for safe training.",
                                    "suggestion": "Consider starting training earlier or selecting a later race date. This plan was generated without considering your race date to ensure optimal progression.",
                                }
                            elif weeks_available < weeks_needed + 2:
                                # Tight but workable
                                buffer = weeks_available - weeks_needed
                                time_warning = {
                                    "code": "TIGHT_SCHEDULE",
                                    "type": "info",
                                    "message": f"This plan requires {weeks_needed} weeks. You have {weeks_available:.1f} weeks available before the race ({rd.strftime('%Y-%m-%d')})—approximately {buffer:.1f} weeks of buffer.",
                                    "suggestion": "This plan was generated without considering your race date. Ensure you can start training immediately to have enough time.",
                                }
                            else:
                                # Plenty of time
                                buffer = weeks_available - weeks_needed
                                recovery_msg = ""
                                if recovery_metadata and recovery_metadata.get(
                                    "inserted"
                                ):
                                    extra_weeks = recovery_metadata.get(
                                        "extra_weeks", 0
                                    )
                                    recovery_msg = f" {extra_weeks} recovery week(s) have been inserted to fill available training time."
                                time_warning = {
                                    "code": "SUFFICIENT_TIME",
                                    "type": "info",
                                    "message": f"This plan requires {weeks_needed} weeks. You have {weeks_available:.1f} weeks available before the race ({rd.strftime('%Y-%m-%d')})—{buffer:.1f} weeks of buffer.{recovery_msg}",
                                    "suggestion": "This plan was generated without considering your race date to ensure optimal progression.",
                                }
                    except Exception as e:
                        logger.warning(f"Error calculating time until race: {e}")

                # Add start date and race date to weeks for frontend
                # Calculate week start dates
                if start_date and race_date:
                    try:
                        from datetime import datetime, date, timedelta

                        if isinstance(race_date, str):
                            rd = datetime.fromisoformat(race_date.split("T")[0]).date()
                        elif isinstance(race_date, date):
                            rd = race_date
                        else:
                            rd = None

                        if rd:
                            # Add week_start_date and week_label to each week
                            for i, week in enumerate(weeks_simple):
                                week_start = start_date + timedelta(weeks=i)
                                month_name = week_start.strftime("%b")  # Jan, Feb, etc.
                                day = week_start.strftime("%d").lstrip(
                                    "0"
                                )  # Remove leading zero
                                week_num = week.get("week_number", i + 1)
                                week["week_start_date"] = week_start.isoformat()
                                week["week_label"] = (
                                    f"Week {week_num} of {month_name} {day}"
                                )

                            # Add race date info
                            race_metadata = {
                                "race_date": rd.isoformat(),
                                "race_date_label": rd.strftime("%b %d, %Y"),
                                "start_date": start_date.isoformat(),
                                "start_date_label": start_date.strftime("%b %d, %Y"),
                            }
                    except Exception as e:
                        logger.warning(f"Error calculating week dates: {e}")
                        race_metadata = None
                else:
                    race_metadata = None

                draft = {
                    "generated_plan": {
                        "weeks": weeks_simple,
                        "race_metadata": race_metadata,
                    },
                    "validation": {
                        "valid": len(violations) == 0,
                        "violations": violations,
                    },
                    "time_assessment": time_warning,  # Add time assessment to draft
                    "recovery_metadata": recovery_metadata,  # Add recovery insertion metadata if applied
                }
                return (jsonify({"status": "success", "draft": draft}), 200)

        return (
            jsonify(
                {
                    "status": "success",
                    "draft": draft,
                }
            ),
            200,
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error generating draft plan: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate draft plan"}), 500


# ✅ POST /api/plan/approve — approve and save a validated draft
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

        # Expect client to send back { validation, plan_request }
        validation = payload.get("validation")
        plan_request = payload.get("plan_request")
        if not isinstance(validation, dict) or not isinstance(plan_request, dict):
            return jsonify({"error": "validation and plan_request are required"}), 400

        from src.services.training_plan.plan_storage_service import PlanStorageService

        with get_session() as session:
            # Use Layer 6 to save the validated plan
            plan_storage = PlanStorageService()
            plan_id = plan_storage.save_validated_plan(
                session=session,
                user_id=str(user_id),
                validated_plan=validation,
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
