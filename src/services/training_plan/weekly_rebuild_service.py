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
from .pace_seed_service import PaceSeed, get_initial_pace_seed, _time_add
from .pass4_workout_details import Pass4WorkoutDetails
from .workout_comparison_service import WorkoutComparisonService
from .workout_utils import extract_pace_zone_from_workout, normalize_segments

# Database models and DAOs
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.dao.plan_workouts_dao import get_workouts_for_week, update_workout
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
    ) -> Dict[str, Any]:
        """
        Rebuild workout details for a specific week.

        Args:
            session: SQLAlchemy database session
            plan_id: Plan ID
            week_num: Week number (1-based)
            previous_week_logs: Optional logs from previous week for adjustments
            initial_seed: Optional initial pace seed (if not provided, regenerates)

        Returns:
            Dict with updated week details and adjustment info
        """
        logger.info(f"Rebuilding week {week_num} for plan {plan_id}")

        # Get plan to access race date and user info
        plan = session.query(Plan).filter_by(id=plan_id).first()
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

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

        # Get or generate initial pace seed
        # OPTIMIZED: Only fetch 12 weeks if it's week 1 (first rebuild)
        # For subsequent weeks, extract seed from previous week's workouts
        if initial_seed is None:
            if week_num == 1:
                # Week 1: Fetch 12 weeks of historical data (only once)
                logger.info(
                    f"[Rebuild] Week 1: Fetching 12 weeks of Strava activities to calculate initial pace seed..."
                )
                import time

                strava_start = time.time()
                from src.services.training_plan.data_collection_service import (
                    DataCollectionService,
                )

                # Get Week 1 totals to seed pace
                first_week_workouts = (
                    all_workouts[:7] if len(all_workouts) >= 7 else all_workouts
                )
                week1_total = sum(w.miles for w in first_week_workouts[:7])
                week1_long = max(
                    (
                        w.miles
                        for w in first_week_workouts
                        if w.workout_type in ("Long Run", "long")
                    ),
                    default=8.0,
                )

                raw_data = DataCollectionService.collect_all_data(
                    session=session,
                    user_id=str(plan.user_id),
                    plan_request={},
                    activity_weeks=12,
                )
                strava_elapsed = time.time() - strava_start
                strava_activities = raw_data.get("strava_activities", [])
                logger.info(
                    f"[Rebuild] Fetched {len(strava_activities)} activities in {strava_elapsed:.1f} seconds"
                )

                logger.info(
                    f"[Rebuild] Generating initial pace seed from historical data..."
                )
                initial_seed = get_initial_pace_seed(
                    strava_activities=strava_activities,
                    plan_week1_total=week1_total,
                    plan_week1_long=week1_long,
                    goal_mp_sec_per_mi=None,
                )
                logger.info(f"[Rebuild] Initial pace seed generated")
            else:
                # Week 2+: Extract pace seed from previous week's workouts
                logger.info(
                    f"[Rebuild] Week {week_num}: Extracting pace seed from previous week's workouts..."
                )
                previous_week_num = week_num - 1
                previous_week_workouts = _find_week_workouts(
                    all_workouts, previous_week_num, plan.race_date
                )

                if previous_week_workouts:
                    # Extract seed from previous week's workout segments
                    extracted_seed = _extract_pace_seed_from_workouts(
                        previous_week_workouts
                    )
                    if extracted_seed:
                        initial_seed = extracted_seed
                        logger.info(
                            f"[Rebuild] Pace seed extracted from previous week's workouts"
                        )
                    else:
                        # Fallback: Fetch 12 weeks if extraction fails
                        logger.warning(
                            f"[Rebuild] Could not extract seed from previous week, fetching 12 weeks as fallback..."
                        )
                        import time

                        strava_start = time.time()
                        from src.services.training_plan.data_collection_service import (
                            DataCollectionService,
                        )

                        raw_data = DataCollectionService.collect_all_data(
                            session=session,
                            user_id=str(plan.user_id),
                            plan_request={},
                            activity_weeks=12,
                        )
                        strava_elapsed = time.time() - strava_start
                        strava_activities = raw_data.get("strava_activities", [])

                        first_week_workouts = (
                            all_workouts[:7] if len(all_workouts) >= 7 else all_workouts
                        )
                        week1_total = sum(w.miles for w in first_week_workouts[:7])
                        week1_long = max(
                            (
                                w.miles
                                for w in first_week_workouts
                                if w.workout_type in ("Long Run", "long")
                            ),
                            default=8.0,
                        )

                        initial_seed = get_initial_pace_seed(
                            strava_activities=strava_activities,
                            plan_week1_total=week1_total,
                            plan_week1_long=week1_long,
                            goal_mp_sec_per_mi=None,
                        )
                        logger.info(
                            f"[Rebuild] Pace seed generated from fallback (12 weeks) in {strava_elapsed:.1f} seconds"
                        )
                else:
                    # No previous week found - use fallback
                    logger.warning(
                        f"[Rebuild] No previous week workouts found, using fallback..."
                    )
                    import time

                    strava_start = time.time()
                    from src.services.training_plan.data_collection_service import (
                        DataCollectionService,
                    )

                    raw_data = DataCollectionService.collect_all_data(
                        session=session,
                        user_id=str(plan.user_id),
                        plan_request={},
                        activity_weeks=12,
                    )
                    strava_elapsed = time.time() - strava_start
                    strava_activities = raw_data.get("strava_activities", [])

                    first_week_workouts = (
                        all_workouts[:7] if len(all_workouts) >= 7 else all_workouts
                    )
                    week1_total = sum(w.miles for w in first_week_workouts[:7])
                    week1_long = max(
                        (
                            w.miles
                            for w in first_week_workouts
                            if w.workout_type in ("Long Run", "long")
                        ),
                        default=8.0,
                    )

                    initial_seed = get_initial_pace_seed(
                        strava_activities=strava_activities,
                        plan_week1_total=week1_total,
                        plan_week1_long=week1_long,
                        goal_mp_sec_per_mi=None,
                    )
                    logger.info(
                        f"[Rebuild] Pace seed generated from fallback in {strava_elapsed:.1f} seconds"
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

        # STAGE 2: Analyze current week (previous week's performance)
        analysis = None
        trends = None
        decision = None
        current_seed = initial_seed
        disable_quality = False

        if previous_week_logs and previous_week_workouts:
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
                WeeklyMetricsService.save_week_metrics(
                    session=session,
                    plan_id=plan_id,
                    analysis=analysis,
                    decision=decision,
                )
                logger.info(f"[Adaptive Pipeline] Metrics and decisions saved")

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

        # Capture original workouts for email (before rebuild)
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
                }
            )

        # Update workouts in database
        updated_count = 0
        for workout_data, db_workout in zip(
            week_with_details["workouts"], week_workouts
        ):
            # Extract values for update
            segments = workout_data.get("segments", [])
            cues = workout_data.get("cues", "")
            new_intensity = workout_data.get("type", db_workout.workout_type)

            # Detect changes using centralized comparison service
            changes = WorkoutComparisonService.detect_changes(db_workout, workout_data)

            # Extract target zone and HR using centralized utilities
            new_target_zone = extract_pace_zone_from_workout(workout_data)
            new_target_hr = workout_data.get("target_hr")

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
                "segments": segments,  # Store as JSON
                "description": cues,  # Update description with cues
                "intensity": new_intensity,  # May update intensity
                "target_zone": new_target_zone or None,  # Save extracted target zone
                "target_hr": new_target_hr or None,  # Save target HR if available
            }

            update_workout(session, db_workout.id, update_data)
            updated_count += 1

        logger.info(
            f"Updated {updated_count} workouts for week {week_num} "
            f"(phase={phase}, quality={allow_quality})"
        )

        # Extract pace_labels from first workout (all workouts have same labels)
        pace_labels = {}
        if week_with_details.get("workouts") and len(week_with_details["workouts"]) > 0:
            pace_labels = week_with_details["workouts"][0].get("pace_labels", {})

        # Build updated workouts list for email
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
        E_min=_time_add(seed.E_min, decision.pace_adjustment_sec),
        E_max=_time_add(seed.E_max, decision.pace_adjustment_sec),
        S_min=_time_add(seed.S_min, decision.pace_adjustment_sec),
        S_max=_time_add(seed.S_max, decision.pace_adjustment_sec),
        M=_time_add(seed.M, decision.pace_adjustment_sec),
        T_min=_time_add(seed.T_min, decision.pace_adjustment_sec),
        T_max=_time_add(seed.T_max, decision.pace_adjustment_sec),
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


def _extract_pace_seed_from_workouts(
    workouts: List[PlanWorkout],
) -> Optional[PaceSeed]:
    """
    Extract pace seed from existing workout segments.

    This allows us to reuse the previous week's pace seed without fetching
    12 weeks of historical data. We extract pace zones from the segments
    stored in the database.

    Args:
        workouts: List of PlanWorkout objects from previous week

    Returns:
        PaceSeed if extraction successful, None otherwise
    """
    # Collect pace targets from workout segments
    easy_paces = []
    steady_paces = []
    marathon_paces = []
    threshold_paces = []

    for workout in workouts:
        if not workout.segments:
            continue

        # Normalize segments using centralized utility
        segments = normalize_segments(workout.segments)
        if not segments:
            continue

        # Extract steps from segments
        steps = None
        if isinstance(segments, dict):
            steps = segments.get("steps", [])
        elif isinstance(segments, list):
            steps = segments
        else:
            continue

        if not steps or not isinstance(steps, list):
            continue

        # Extract pace targets from each step
        for step in steps:
            if not isinstance(step, dict):
                continue

            target = step.get("target")
            intensity = step.get("intensity", "").upper()
            name = step.get("name", "").upper()

            if not target:
                continue

            # Handle both dict and simple format
            if isinstance(target, dict):
                low = target.get("low")
                high = target.get("high")
            elif isinstance(target, (int, float)):
                low = high = target
            else:
                continue

            if low is None or high is None:
                continue

            # Categorize by intensity/name
            if (
                intensity == "EASY"
                or "EASY" in name
                or "WARM" in name
                or "COOL" in name
            ):
                easy_paces.extend([low, high])
            elif intensity == "STEADY" or "STEADY" in name or "ENDURANCE" in name:
                steady_paces.extend([low, high])
            elif intensity == "MARATHON" or "MARATHON" in name:
                marathon_paces.append((low + high) / 2)  # Single value
            elif intensity == "THRESHOLD" or "THRESHOLD" in name or "TEMPO" in name:
                threshold_paces.extend([low, high])

    # Calculate pace zones from collected paces
    # If we have enough data, use median/mean; otherwise return None
    if not (easy_paces or steady_paces or marathon_paces or threshold_paces):
        logger.debug("No pace data found in workout segments")
        return None

    # Calculate E zone (Easy)
    E_min = E_max = None
    if easy_paces:
        sorted_easy = sorted(easy_paces)
        E_min = sorted_easy[0]  # Minimum easy pace
        E_max = sorted_easy[-1]  # Maximum easy pace
        # If we have few samples, create a range around median
        if len(sorted_easy) < 4:
            median_easy = sorted_easy[len(sorted_easy) // 2]
            E_min = median_easy - 15  # 15 seconds slower
            E_max = median_easy + 45  # 45 seconds faster

    # Calculate S zone (Steady)
    S_min = S_max = None
    if steady_paces:
        sorted_steady = sorted(steady_paces)
        S_min = sorted_steady[0]
        S_max = sorted_steady[-1]
        if len(sorted_steady) < 4:
            median_steady = sorted_steady[len(sorted_steady) // 2]
            S_min = median_steady - 15
            S_max = median_steady + 15

    # Calculate M pace (Marathon - single value)
    M = None
    if marathon_paces:
        M = sum(marathon_paces) / len(marathon_paces)
    elif E_min and E_max:
        # Estimate M from E: M is ~60s faster than E
        median_easy = (E_min + E_max) / 2
        M = median_easy - 60

    # Calculate T zone (Threshold)
    T_min = T_max = None
    if threshold_paces:
        sorted_threshold = sorted(threshold_paces)
        T_min = sorted_threshold[0]
        T_max = sorted_threshold[-1]
        if len(sorted_threshold) < 4:
            median_threshold = sorted_threshold[len(sorted_threshold) // 2]
            T_min = median_threshold - 5
            T_max = median_threshold + 5
    elif M:
        # Estimate T from M: T is ~20-30s faster than M
        T_min = M - 30
        T_max = M - 20

    # Validate we have at least E and M (required)
    if E_min is None or E_max is None or M is None:
        logger.warning(
            f"Insufficient pace data extracted: E={E_min}-{E_max}, M={M}, "
            f"S={S_min}-{S_max}, T={T_min}-{T_max}"
        )
        return None

    # Use estimates for missing zones
    if S_min is None or S_max is None:
        median_easy = (E_min + E_max) / 2
        S_min = median_easy - 15
        S_max = median_easy + 15

    if T_min is None or T_max is None:
        T_min = M - 30
        T_max = M - 20

    # Estimate week1_long_cap (use average of long runs if available)
    long_runs = [w.miles for w in workouts if "long" in w.workout_type.lower()]
    week1_long_cap = max(long_runs) if long_runs else 8.0

    seed = PaceSeed(
        E_min=float(E_min),
        E_max=float(E_max),
        S_min=float(S_min),
        S_max=float(S_max),
        M=float(M),
        T_min=float(T_min),
        T_max=float(T_max),
        week1_long_cap=week1_long_cap,
    )

    logger.info(
        f"Extracted pace seed: E={E_min:.1f}-{E_max:.1f}s/mi, "
        f"S={S_min:.1f}-{S_max:.1f}s/mi, M={M:.1f}s/mi, "
        f"T={T_min:.1f}-{T_max:.1f}s/mi"
    )

    return seed
