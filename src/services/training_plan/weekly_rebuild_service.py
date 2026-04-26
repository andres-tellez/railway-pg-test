"""
Weekly Rebuild Service - Orchestrator

Purpose:
    Orchestrate the adaptive training plan rebuild pipeline:
    1. Create enhanced week logs (Stage 1)
    2. Analyze week performance (Stage 2)
    3. Analyze trends (Stage 3)
    4. Calculate adjustments (Stage 4)
    5. Persist metrics and decisions (Stage 5)
    6. Apply adjustments and rebuild workouts

This service coordinates all stages but delegates specific logic
to specialized services.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session
import logging

# Stage services (NEW)
from .week_log_service import fetch_week_logs
from .week_analysis_service import WeekAnalysisService
from .trend_analysis_service import TrendAnalysisService
from .adaptive_adjustment_service import AdaptiveAdjustmentService
from .weekly_metrics_service import WeeklyMetricsService

# Existing services
from src.services.training_plan.pace import PaceSeed, get_initial_pace_seed

# Use the refactored v2 workout detail service for rebuilds
from src.services.training_plan.v2.pass4_workout_details_v2 import (
    Pass4WorkoutDetails,
)
from .workout_comparison_service import WorkoutComparisonService
from .workout_utils import extract_pace_zone_from_workout

# Database models and DAOs
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.dao.plan_workouts_dao import get_workouts_for_week, update_workout
from src.db.dao.user_profile_dao import get_user_profile
from src.utils.date_helpers import date_to_day_name, get_week_start_for_date

logger = logging.getLogger(__name__)


class WeeklyRebuildService:
    """Service for rebuilding workout details for a specific week."""

    @staticmethod
    def rebuild_week(
        session: Session,
        plan_id: int,
        week_num: int,
        previous_week_logs: Optional[List] = None,
        initial_seed: Optional[PaceSeed] = None,
        skip_adaptive_adjustments: bool = False,
    ) -> Dict[str, Any]:
        """
        Rebuild workout details for a specific week.

        Args:
            session: SQLAlchemy database session
            plan_id: Plan ID
            week_num: Week number (1-based)
            previous_week_logs: Optional logs from previous week for adjustments
            initial_seed: Optional initial pace seed (if not provided, regenerates)
            skip_adaptive_adjustments: If True, use initial_seed directly without adaptive adjustments
                                      (useful for admin tools to force new paces)

        Returns:
            Dict with updated week details and adjustment info
        """
        logger.info(f"Rebuilding week {week_num} for plan {plan_id}")

        # Get plan to access race date and user info
        plan = session.query(Plan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        # Phase F 3F.4 — log Layer C hints when present (preference signals for operators).
        try:
            from uuid import UUID as _UUID

            from src.services.coach.user_plan_memory_service import (
                coach_memory_hints_for_plan_generation,
            )

            _hints = coach_memory_hints_for_plan_generation(
                session, _UUID(str(plan.user_id))
            )
            if _hints:
                logger.info(
                    "[WeeklyRebuild] coach_memory_hints count=%s plan_id=%s",
                    len(_hints),
                    plan_id,
                )
        except Exception:
            logger.debug(
                "[WeeklyRebuild] coach_memory_hints unavailable", exc_info=True
            )

        if not plan.race_date:
            raise ValueError(f"Plan {plan_id} has no race date")

        # Calculate week dates
        # Week N starts N weeks before race (approximately)
        # For simplicity, calculate from plan creation or race date backwards
        # This is simplified - you may need to adjust based on your week calculation logic

        # Get all workouts to find the actual week structure
        all_workouts = (
            session.query(PlanWorkout)
            .filter_by(plan_id=plan_id)
            .order_by(PlanWorkout.date)
            .all()
        )

        if not all_workouts:
            raise ValueError(f"No workouts found for plan {plan_id}")

        # Find workouts for the target week
        # Simplified: assume weeks are sequential and group by week
        # In production, you'd track week_number or calculate from race date
        week_workouts = _find_week_workouts(all_workouts, week_num, plan.race_date)

        if not week_workouts:
            raise ValueError(f"No workouts found for week {week_num}")

        # Calculate week start/end from workouts
        week_start = min(w.date for w in week_workouts)
        week_end = max(w.date for w in week_workouts)

        # Get or generate initial pace seed using performance-based calculation
        # The new SQL-based approach is fast and always uses recent run data
        if initial_seed is None:
            logger.info(
                f"[Rebuild] Calculating initial pace seed using performance-based method..."
            )

            # Get week1_long from first week's long run
            first_week_workouts = (
                all_workouts[:7] if len(all_workouts) >= 7 else all_workouts
            )
            week1_long = max(
                (
                    w.miles
                    for w in first_week_workouts
                    if w.workout_type in ("Long Run", "long")
                ),
                default=8.0,
            )

            # Use new performance-based calculation (SQL-based, fast)
            initial_seed = get_initial_pace_seed(
                session=session,
                user_id=str(plan.user_id),
                week1_long=week1_long,
                lookback_weeks=6,
            )
            logger.info(
                f"[Rebuild] Initial pace seed generated using performance-based method"
            )

        # ========================================================================
        # ADAPTIVE PIPELINE: 5-Stage Analysis and Adjustment
        # ========================================================================

        # Determine phase (simplified - you may store phase in plan or calculate)
        total_weeks = len(all_workouts) // 7  # Approximate total weeks
        phase = _determine_phase(week_num, total_weeks)
        weeks_remaining = total_weeks - week_num + 1

        # STAGE 1: Create enhanced week logs (previous week)
        previous_week_num = week_num - 1
        previous_week_logs = None
        previous_week_workouts = None

        if previous_week_num > 0:
            logger.info(
                f"[Adaptive Pipeline] Stage 1: Creating enhanced week logs for week {previous_week_num}"
            )
            previous_week_workouts = _find_week_workouts(
                all_workouts, previous_week_num, plan.race_date
            )

            if previous_week_workouts:
                # Fetch week logs from database/Strava
                previous_week_logs = fetch_week_logs(
                    session=session,
                    plan_id=plan_id,
                    week_num=previous_week_num,
                    race_date=plan.race_date,
                    request_logs=None,  # Use database/Strava data
                )
                logger.info(
                    f"[Adaptive Pipeline] Created {len(previous_week_logs)} week log entries"
                )

        # Lean aggregate-based seed nudge (matcher-independent)
        try:
            if (
                previous_week_logs
                and previous_week_workouts
                and initial_seed is not None
            ):
                from .data_collection_service import DataCollectionService
                from .pacing_config import CONFIG
                from .weekly_aggregates import compute_weekly_aggregates_from_activities

                # Determine previous week bounds
                prev_week_start = min(w.date for w in previous_week_workouts)
                prev_week_end = max(w.date for w in previous_week_workouts)

                # Fetch a small recent window and filter to previous week
                activities_all = DataCollectionService.fetch_strava_activities(
                    session=session,
                    user_id=str(plan.user_id),
                    weeks=4,
                    activity_type="Run",
                )
                prev_week_acts = [
                    a
                    for a in activities_all
                    if a.get("date")
                    and prev_week_start.isoformat()
                    <= a["date"]
                    <= prev_week_end.isoformat()
                ]

                aggs = compute_weekly_aggregates_from_activities(
                    prev_week_acts,
                    easyish_min_mi=CONFIG.easyish_min_mi,
                    easyish_max_mi=CONFIG.easyish_max_mi,
                    lr_min_mi=CONFIG.lr_min_qualifying_mi,
                )

                current_seed = initial_seed
                easy_med = aggs.get("weekly_easyish_median_sec")
                # Optionally include LR if it was executed aerobically (within easy band)
                lr_pace = aggs.get("weekly_lr_pace_sec")
                if lr_pace is not None:
                    e_min = current_seed.E_min
                    e_max = current_seed.E_max
                    if e_min <= float(lr_pace) <= e_max:
                        if easy_med:
                            easy_med = (float(easy_med) + float(lr_pace)) / 2.0
                        else:
                            easy_med = float(lr_pace)

                if easy_med:
                    seed_center = (current_seed.E_min + current_seed.E_max) / 2.0
                    diff = float(easy_med) - float(seed_center)
                    if abs(diff) > CONFIG.easy_diff_trigger_sec:
                        # Clamp to weekly cap
                        delta = max(
                            -CONFIG.weekly_adjust_cap_sec,
                            min(CONFIG.weekly_adjust_cap_sec, diff),
                        )
                        logger.info(
                            f"[Adaptive Pipeline] Aggregate-based pace nudge: "
                            f"weekly_median_effective={easy_med:.1f}s/mi, seed_center={seed_center:.1f}s/mi, "
                            f"delta={delta:.1f}s"
                        )
                        current_seed = PaceSeed(
                            E_min=current_seed.E_min + delta,
                            E_max=current_seed.E_max + delta,
                            S_min=current_seed.S_min + delta,
                            S_max=current_seed.S_max + delta,
                            M=current_seed.M + delta,
                            T_min=current_seed.T_min + delta,
                            T_max=current_seed.T_max + delta,
                            week1_long_cap=current_seed.week1_long_cap,
                        )
                        # Update initial_seed so downstream stages use the nudged seed
                        initial_seed = current_seed
        except Exception as e:
            logger.warning(
                f"[Adaptive Pipeline] Skipping aggregate-based nudge due to error: {e}"
            )

        # STAGE 2: Analyze current week (previous week's performance)
        analysis = None
        trends = None
        decision = None
        current_seed = initial_seed
        disable_quality = False

        # If skip_adaptive_adjustments is True, use the provided seed directly without adjustments
        # This allows admin tools to force new paces regardless of previous week performance
        if skip_adaptive_adjustments:
            if current_seed is None:
                logger.error(
                    f"[Rebuild] CRITICAL: skip_adaptive_adjustments=True but initial_seed is None!"
                )
                raise ValueError(
                    "Cannot skip adaptive adjustments without initial_seed"
                )
            logger.info(
                f"[Rebuild] Using explicitly provided pace seed (skipping adaptive adjustments per request): "
                f"E={current_seed.E_min}-{current_seed.E_max}s/mi, M={current_seed.M}s/mi"
            )

        if (
            previous_week_logs
            and previous_week_workouts
            and not skip_adaptive_adjustments
        ):
            try:
                logger.info(
                    f"[Adaptive Pipeline] Stage 2: Analyzing week {previous_week_num} performance"
                )

                # Calculate previous week start date
                previous_week_start = get_week_start_for_date(
                    min(w.date for w in previous_week_workouts)
                )

                # Get previous week metrics for load delta calculation
                previous_week_metrics = None
                try:
                    from .weekly_metrics_service import WeeklyMetricsService

                    historical = WeeklyMetricsService.get_historical_metrics(
                        session, plan_id, weeks=1
                    )
                    if historical and historical[0].week_num == previous_week_num - 1:
                        previous_week_metrics = historical[0]
                except Exception as e:
                    logger.debug(f"Could not fetch previous week metrics: {e}")

                analysis = WeekAnalysisService.analyze_week(
                    session=session,
                    week_logs=previous_week_logs,
                    planned_workouts=previous_week_workouts,
                    week_num=previous_week_num,
                    week_start_date=previous_week_start,
                    previous_week_metrics=previous_week_metrics,
                )
                logger.info(
                    f"[Adaptive Pipeline] Analysis complete: "
                    f"volume={analysis.volume_score:.1f}%, "
                    f"intensity={analysis.intensity_score:.1f}%, "
                    f"consistency={analysis.consistency_score:.1f}%"
                )

                # STAGE 3: Analyze trends
                logger.info(f"[Adaptive Pipeline] Stage 3: Analyzing trends")
                trends = TrendAnalysisService.analyze_trends(
                    session=session,
                    current_week_analysis=analysis,
                    plan_id=plan_id,
                    lookback_weeks=2,
                )
                logger.info(
                    f"[Adaptive Pipeline] Trends: volume={trends.volume_trend}, "
                    f"intensity={trends.intensity_trend}, pace={trends.pace_trend}"
                )

                # STAGE 4: Calculate adjustments
                logger.info(
                    f"[Adaptive Pipeline] Stage 4: Calculating phase-aware adjustments"
                )
                decision = AdaptiveAdjustmentService.calculate_adjustment(
                    analysis=analysis,
                    trends=trends,
                    current_seed=initial_seed,
                    phase=phase,
                    weeks_remaining=weeks_remaining,
                )
                logger.info(
                    f"[Adaptive Pipeline] Decision: {decision.decision_type}, "
                    f"volume_change={decision.volume_change_pct}%, "
                    f"pace_adjustment={decision.pace_adjustment_sec}s"
                )

                # Apply adjustments to pace seed
                current_seed = _apply_decision_to_seed(initial_seed, decision)
                disable_quality = decision.disable_quality_workouts

                # STAGE 5: Persist metrics and decisions
                logger.info(
                    f"[Adaptive Pipeline] Stage 5: Persisting metrics and decisions"
                )
                try:
                    WeeklyMetricsService.save_week_metrics(
                        session=session,
                        plan_id=plan_id,
                        analysis=analysis,
                        decision=decision,
                    )
                    logger.info(f"[Adaptive Pipeline] Metrics and decisions saved")
                except Exception as e:
                    # If persistence fails (e.g., tables don't exist), log warning but continue
                    error_str = str(e).lower()
                    if (
                        "does not exist" in error_str
                        or "undefinedtable" in error_str
                        or "infailed" in error_str
                    ):
                        logger.warning(
                            f"⚠️  [Adaptive Pipeline] Could not persist metrics (tables may not exist yet): {e}. "
                            f"Continuing without persistence..."
                        )
                    else:
                        # Re-raise if it's a different error
                        raise

            except Exception as e:
                logger.error(
                    f"[Adaptive Pipeline] Error in adaptive pipeline: {e}",
                    exc_info=True,
                )
                # Fallback to original behavior if pipeline fails
                logger.warning("Falling back to simple adjustment logic")
                if previous_week_logs:
                    from .weekly_adjuster import adjust_seed_from_week

                    current_seed, disable_quality = adjust_seed_from_week(
                        initial_seed, previous_week_logs
                    )

        # Convert workouts to plan format
        week_plan = {
            "week_number": week_num,
            "phase": phase,
            "workouts": [
                {
                    "day": date_to_day_name(w.date),
                    "type": _normalize_workout_type(w.workout_type),
                    "miles": float(w.miles),
                    "distance_miles": float(w.miles),
                }
                for w in week_workouts
            ],
        }

        # Rebuild details using Pass 4
        logger.info(
            f"[Rebuild] Generating workout details with Pass4... (may take 10-30 seconds if calling OpenAI)"
        )
        import time

        pass4_start = time.time()
        pass4 = Pass4WorkoutDetails()
        allow_quality = (phase in ("Build", "Peak")) and not disable_quality

        week_with_details = pass4.add_details_to_week(
            week=week_plan,
            seed=current_seed,
            allow_quality=allow_quality,
        )
        pass4_elapsed = time.time() - pass4_start
        logger.info(
            f"[Rebuild] Workout details generated for {len(week_with_details.get('workouts', []))} workouts in {pass4_elapsed:.1f} seconds"
        )

        # Track changes for email notification
        workout_changes = []

        # Capture original workouts for email (before rebuild, include existing segments)
        original_workouts = []
        for db_workout in week_workouts:
            original_workouts.append(
                {
                    "date": (
                        db_workout.date.isoformat()
                        if hasattr(db_workout.date, "isoformat")
                        else str(db_workout.date)
                    ),
                    "day": date_to_day_name(db_workout.date),
                    "workout_type": db_workout.workout_type,
                    "miles": float(db_workout.miles or 0),
                    "description": db_workout.description or "",
                    "target_zone": db_workout.target_zone or "",
                    "target_hr": db_workout.target_hr or "",
                    "segments": db_workout.segments,  # Include existing segments for comparison
                }
            )

        # Update workouts in database
        updated_count = 0
        segments_saved_count = 0
        segments_missing_count = 0

        for workout_data, db_workout in zip(
            week_with_details["workouts"], week_workouts
        ):
            # Extract values for update
            segments = workout_data.get("segments")
            cues = workout_data.get("cues", "")
            new_intensity = workout_data.get("type", db_workout.workout_type)

            # Detect changes using centralized comparison service
            changes = WorkoutComparisonService.detect_changes(db_workout, workout_data)

            # Extract target zone and HR using centralized utilities
            new_target_zone = extract_pace_zone_from_workout(workout_data)
            new_target_hr = workout_data.get("target_hr")

            # Calculate HR zone if not provided by Pass4
            if not new_target_hr:
                new_target_hr = WeeklyRebuildService._calculate_hr_zone_for_workout(
                    db_workout, str(plan.user_id), session
                )

            # Always store change record (include all workouts, even if no changes)
            workout_changes.append(
                {
                    "date": (
                        db_workout.date.isoformat()
                        if hasattr(db_workout.date, "isoformat")
                        else str(db_workout.date)
                    ),
                    "workout_type": db_workout.workout_type,
                    "miles": db_workout.miles or workout_data.get("miles", 0),
                    "changes": changes,  # Empty list if no changes
                }
            )

            # Build update data including all fields that should be saved
            update_data = {
                "description": cues,  # Update description with cues
                "intensity": new_intensity,  # May update intensity
                "target_zone": new_target_zone or None,  # Save extracted target zone
                "target_hr": new_target_hr or None,  # Save target HR if available
            }

            # Keep pace_ranges in sync with the active seed so table and UI match
            if current_seed is None:
                logger.warning(
                    f"[Rebuild] Cannot set pace_ranges: current_seed is None for workout {db_workout.id} "
                    f"({db_workout.date}, {db_workout.workout_type})"
                )
            else:
                try:
                    update_data["pace_ranges"] = {
                        "E": [float(current_seed.E_min), float(current_seed.E_max)],
                        "S": [float(current_seed.S_min), float(current_seed.S_max)],
                        "M": [float(current_seed.M), float(current_seed.M)],
                        "T": [float(current_seed.T_min), float(current_seed.T_max)],
                    }

                    # ALWAYS set target_zone from current_seed to keep in sync with pace_ranges
                    # This ensures frontend sees updated pace even if extract_pace_zone_from_workout fails
                    from .workout_utils import (
                        get_workout_pace_label_key,
                        pace_range_to_str,
                    )

                    pace_key = get_workout_pace_label_key(db_workout.workout_type or "")

                    if pace_key == "E":
                        target_zone_str = pace_range_to_str(
                            current_seed.E_min, current_seed.E_max
                        )
                    elif pace_key == "S":
                        target_zone_str = pace_range_to_str(
                            current_seed.S_min, current_seed.S_max
                        )
                    elif pace_key == "M":
                        target_zone_str = pace_range_to_str(
                            current_seed.M, current_seed.M
                        )
                    elif pace_key == "T":
                        target_zone_str = pace_range_to_str(
                            current_seed.T_min, current_seed.T_max
                        )
                    else:
                        # Default to Easy
                        target_zone_str = pace_range_to_str(
                            current_seed.E_min, current_seed.E_max
                        )

                    # Override target_zone with value from seed (single source of truth)
                    update_data["target_zone"] = target_zone_str

                    logger.info(
                        f"[Rebuild] Set pace_ranges and target_zone for workout {db_workout.id} ({db_workout.date}): "
                        f"E={current_seed.E_min:.1f}-{current_seed.E_max:.1f}s/mi, "
                        f"target_zone={target_zone_str} (from {pace_key} zone)"
                    )
                except Exception as e:
                    # Log the actual error instead of silently failing
                    logger.error(
                        f"[Rebuild] Failed to set pace_ranges/target_zone for workout {db_workout.id} "
                        f"({db_workout.date}, {db_workout.workout_type}): {e}",
                        exc_info=True,
                    )
                    # Log and continue - don't break the whole rebuild if pace_ranges fails
                    # This way we can see what's failing without stopping all updates

            # ALWAYS save segments if they exist (critical for Garmin automation)
            # Segments should be a dict with "steps" array from pass4_workout_details
            if segments is not None:
                # Validate segments structure - must be a dict with "steps" key
                if isinstance(segments, dict):
                    steps = segments.get("steps", [])
                    step_count = len(steps) if isinstance(steps, list) else 0

                    # Only save if segments has valid structure (steps array)
                    if step_count > 0 or "steps" in segments:
                        update_data["segments"] = segments
                        segments_saved_count += 1
                        logger.debug(
                            f"Saving segments for workout {db_workout.id} ({db_workout.date}): "
                            f"{step_count} steps, type={db_workout.workout_type}"
                        )
                    else:
                        # Segments dict exists but has no steps - log warning
                        logger.warning(
                            f"Segments for workout {db_workout.id} is missing 'steps' array. "
                            f"Structure: {list(segments.keys())}"
                        )
                        # Still try to save it (maybe valid empty structure)
                        update_data["segments"] = segments
                        segments_saved_count += 1
                else:
                    # Segments exists but is not a dict - log warning but still try to save
                    logger.warning(
                        f"Segments for workout {db_workout.id} is not a dict: {type(segments)}. "
                        f"Saving anyway."
                    )
                    update_data["segments"] = segments
                    segments_saved_count += 1
            else:
                # Only log missing segments for workouts that should have them (non-rest days)
                if db_workout.miles and db_workout.miles > 0:
                    logger.warning(
                        f"No segments found for workout {db_workout.id} on {db_workout.date} "
                        f"({db_workout.workout_type}, {db_workout.miles:.1f} mi) - "
                        f"workout_data keys: {list(workout_data.keys())}"
                    )
                    segments_missing_count += 1

            # Log what we're updating (especially pace_ranges)
            if "pace_ranges" in update_data:
                logger.info(
                    f"[Rebuild] Updating workout {db_workout.id} ({db_workout.date}): "
                    f"pace_ranges={update_data['pace_ranges']}"
                )
            else:
                logger.warning(
                    f"[Rebuild] WARNING: pace_ranges NOT in update_data for workout {db_workout.id} ({db_workout.date})"
                )

            update_workout(session, db_workout.id, update_data)
            updated_count += 1

        # Log summary of segments saved
        logger.info(
            f"Segments saved: {segments_saved_count}/{updated_count} workouts "
            f"({segments_missing_count} missing for workouts with distance > 0)"
        )

        # Count how many workouts got pace_ranges updated (refresh from DB to get latest values)
        session.flush()  # Ensure all updates are flushed
        refreshed_workouts = (
            session.query(PlanWorkout)
            .filter(PlanWorkout.id.in_([w.id for w in week_workouts]))
            .all()
        )
        pace_ranges_count = sum(
            1 for w in refreshed_workouts if w.pace_ranges is not None
        )

        logger.info(
            f"Updated {updated_count} workouts for week {week_num} "
            f"(phase={phase}, quality={allow_quality}, pace_ranges set on {pace_ranges_count}/{updated_count})"
        )

        # Extract pace_labels from first workout (all workouts have same labels)
        pace_labels = {}
        if week_with_details.get("workouts") and len(week_with_details["workouts"]) > 0:
            pace_labels = week_with_details["workouts"][0].get("pace_labels", {})

        # Build updated workouts list for email (include segments for detailed display)
        updated_workouts = []
        for workout_data, db_workout in zip(
            week_with_details["workouts"], week_workouts
        ):
            updated_workouts.append(
                {
                    "date": (
                        db_workout.date.isoformat()
                        if hasattr(db_workout.date, "isoformat")
                        else str(db_workout.date)
                    ),
                    "day": workout_data.get("day", date_to_day_name(db_workout.date)),
                    "workout_type": workout_data.get("type", ""),
                    "miles": float(
                        workout_data.get("miles")
                        or workout_data.get("distance_miles", 0)
                    ),
                    "description": workout_data.get("cues", ""),
                    "target_zone": extract_pace_zone_from_workout(workout_data),
                    "target_hr": workout_data.get("target_hr") or "",
                    "segments": workout_data.get(
                        "segments"
                    ),  # Include segments for email display
                }
            )

        return {
            "week_number": week_num,
            "phase": phase,
            "workouts": week_with_details["workouts"],
            "pace_adjusted": previous_week_logs is not None,
            "quality_disabled": disable_quality,
            "pace_labels": pace_labels,
            "workout_changes": workout_changes,  # Include changes for email
            "original_workouts": original_workouts,  # Original plan before rebuild
            "updated_workouts": updated_workouts,  # Updated plan after rebuild
            "adjustment_decision": decision,  # Include decision for debugging/email
        }

    @staticmethod
    def _calculate_hr_zone_for_workout(
        db_workout: PlanWorkout, user_id: str, session: Session
    ) -> Optional[str]:
        """
        Calculate HR zone for a workout if not already set.
        Uses the same logic as plan_storage_service.
        """
        # Import here to avoid circular dependency
        from src.services.training_plan.plan_storage_service import PlanStorageService

        # Get user profile
        user_profile = get_user_profile(session, user_id)

        # Use run_type_key if available, otherwise infer from workout_type
        run_type_key = db_workout.run_type_key
        if not run_type_key:
            # Infer from workout_type
            workout_type_lower = (db_workout.workout_type or "").lower()
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

        return PlanStorageService._calculate_hr_zone(run_type_key, user_profile)


def _apply_decision_to_seed(
    seed: PaceSeed,
    decision: "AdjustmentDecision",
) -> PaceSeed:
    """
    Apply adjustment decision to pace seed.

    Adjusts all pace zones by the pace_adjustment_sec amount.
    Volume adjustments are handled separately in workout generation.

    Args:
        seed: Current pace seed
        decision: Adjustment decision

    Returns:
        Adjusted pace seed
    """
    if decision.pace_adjustment_sec == 0:
        return seed

    # Apply pace adjustment to all zones
    return PaceSeed(
        E_min=seed.E_min + decision.pace_adjustment_sec,
        E_max=seed.E_max + decision.pace_adjustment_sec,
        S_min=seed.S_min + decision.pace_adjustment_sec,
        S_max=seed.S_max + decision.pace_adjustment_sec,
        M=seed.M + decision.pace_adjustment_sec,
        T_min=seed.T_min + decision.pace_adjustment_sec,
        T_max=seed.T_max + decision.pace_adjustment_sec,
        week1_long_cap=seed.week1_long_cap,
    )


def _find_week_workouts(
    all_workouts: List[PlanWorkout],
    week_num: int,
    race_date: date,
) -> List[PlanWorkout]:
    """
    Find workouts for a specific week.

    Simplified: calculate week dates from race date backwards.
    """
    # Calculate weeks from race date
    # Week N is N weeks before race week
    # Race week is week 0, previous week is week 1, etc.
    weeks_before_race = week_num  # Adjust based on your week numbering

    # Calculate approximate week start (Monday of that week)
    from src.utils.date_helpers import get_week_start_for_date

    target_week_start = race_date - timedelta(weeks=weeks_before_race)
    week_start = get_week_start_for_date(target_week_start)
    week_end = week_start + timedelta(days=6)

    # Find workouts in that date range
    week_workouts = [w for w in all_workouts if week_start <= w.date <= week_end]

    return week_workouts


def _normalize_workout_type(workout_type: str) -> str:
    """Normalize workout type to standard format (easy, steady, endurance, long)."""
    workout_type_lower = workout_type.lower()
    if "easy" in workout_type_lower or "recovery" in workout_type_lower:
        return "easy"
    if "steady" in workout_type_lower or "aerobic" in workout_type_lower:
        return "steady"
    if "endurance" in workout_type_lower or "medium-long" in workout_type_lower:
        return "endurance"
    if "long" in workout_type_lower:
        return "long"
    return "easy"  # Default fallback


def _determine_phase(week_num: int, total_weeks: int) -> str:
    """
    Determine training phase based on week number.

    Simplified: assume Base → Build → Peak → Taper
    """
    if week_num <= total_weeks * 0.4:
        return "Base"
    elif week_num <= total_weeks * 0.7:
        return "Build"
    elif week_num <= total_weeks * 0.9:
        return "Peak"
    else:
        return "Taper"
