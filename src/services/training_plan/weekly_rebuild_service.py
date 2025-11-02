"""
Weekly Rebuild Service

Purpose:
    Rebuild workout details for a specific week using adjusted pace seed.
    Used in rolling mode to adapt upcoming weeks based on previous week's completion.

Integration:
    Called by weekly rebuild endpoint to regenerate upcoming week with adjustments.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session
import logging

from .pace_seed_service import PaceSeed, get_initial_pace_seed
from .weekly_adjuster import adjust_seed_from_week
from .pass4_workout_details import Pass4WorkoutDetails
from .week_log_service import fetch_week_logs
from src.db.models.plans import Plan
from src.db.models.plan_workouts import PlanWorkout
from src.db.dao.plan_workouts_dao import get_workouts_for_week, update_workout

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

        # Adjust seed based on previous week logs
        current_seed = initial_seed
        disable_quality = False

        if previous_week_logs:
            logger.info(
                f"Adjusting pace seed based on previous week logs ({len(previous_week_logs)} runs)"
            )
            current_seed, disable_quality = adjust_seed_from_week(
                initial_seed, previous_week_logs
            )

        # Determine phase (simplified - you may store phase in plan or calculate)
        phase = _determine_phase(
            week_num, len(all_workouts) // 7
        )  # Approximate total weeks

        # Convert workouts to plan format
        week_plan = {
            "week_number": week_num,
            "phase": phase,
            "workouts": [
                {
                    "day": _date_to_day_name(w.date),
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

        # Update workouts in database
        updated_count = 0
        for workout_data, db_workout in zip(
            week_with_details["workouts"], week_workouts
        ):
            # Update segments and related fields
            segments = workout_data.get("segments", [])
            cues = workout_data.get("cues", "")
            pace_labels = workout_data.get("pace_labels", {})
            new_intensity = workout_data.get("type", db_workout.workout_type)

            # Track changes before updating
            changes = []

            # Helper function to normalize segments (used in multiple places)
            import json

            def normalize_segments(seg_data):
                """Normalize segments to dict for comparison."""
                if not seg_data:
                    return None
                if isinstance(seg_data, dict):
                    return seg_data
                if isinstance(seg_data, str):
                    try:
                        return json.loads(seg_data)
                    except (json.JSONDecodeError, TypeError):
                        return None
                return None

            # Compare description/cues
            old_description = db_workout.description or ""
            new_description = cues or ""
            if old_description != new_description:
                changes.append(
                    {
                        "field": "Description/Cues",
                        "before": (
                            old_description[:50] + "..."
                            if len(old_description) > 50
                            else old_description
                        ),
                        "after": (
                            new_description[:50] + "..."
                            if len(new_description) > 50
                            else new_description
                        ),
                    }
                )

            # Compare intensity
            old_intensity = db_workout.intensity or db_workout.workout_type or ""
            if old_intensity != new_intensity:
                changes.append(
                    {
                        "field": "Intensity",
                        "before": old_intensity,
                        "after": new_intensity,
                    }
                )

            # Compare segments with detailed information
            # Normalize both to dict for proper comparison
            old_segments_normalized = normalize_segments(db_workout.segments)
            new_segments_normalized = normalize_segments(segments)

            # Deep compare by converting both to JSON strings
            old_seg_json = (
                json.dumps(old_segments_normalized, sort_keys=True)
                if old_segments_normalized
                else None
            )
            new_seg_json = (
                json.dumps(new_segments_normalized, sort_keys=True)
                if new_segments_normalized
                else None
            )

            if old_seg_json != new_seg_json:
                # Parse segments to extract detailed information
                # Helper to format segment details
                def format_segment_details(seg_data):
                    """Format segment data into human-readable string."""
                    if not seg_data:
                        return "None"

                    # Normalize to dict
                    normalized = normalize_segments(seg_data)
                    if not normalized:
                        return "None"

                    # Extract steps information
                    steps = (
                        normalized.get("steps", [])
                        if isinstance(normalized, dict)
                        else []
                    )
                    if not steps:
                        return "No steps"

                    # Build summary of workout structure
                    step_summaries = []
                    for step in steps[:5]:  # Limit to first 5 intervals
                        step_type = step.get("type", "unknown")
                        value = step.get("value", 0)
                        unit = step.get("unit", "mi")
                        target = step.get("target", {})

                        # Format pace information
                        pace_info = ""
                        if isinstance(target, dict):
                            pace_min = target.get("paceMin")
                            pace_max = target.get("paceMax")
                            if pace_min and pace_max:
                                # Convert seconds per mile to MM:SS
                                def sec_to_pace(sec):
                                    mins = int(sec // 60)
                                    secs = int(sec % 60)
                                    return f"{mins}:{secs:02d}"

                                pace_info = f" @ {sec_to_pace(pace_min)}-{sec_to_pace(pace_max)}/mi"

                        step_summaries.append(
                            f"{step_type.capitalize()}: {value} {unit}{pace_info}"
                        )

                    summary = "; ".join(step_summaries)
                    if len(steps) > 5:
                        summary += f" (+ {len(steps) - 5} more)"

                    return summary or f"{len(steps)} steps"

                old_seg_str = format_segment_details(old_segments_normalized)
                new_seg_str = format_segment_details(new_segments_normalized)

                changes.append(
                    {
                        "field": "Workout Structure",
                        "before": old_seg_str,
                        "after": new_seg_str,
                    }
                )

            # Compare target zone (pace zone)
            # Try to extract from multiple sources
            old_target_zone = db_workout.target_zone or ""

            def extract_pace_zone_string(workout_data):
                """Extract pace zone string from workout data."""
                # First try direct target_zone
                target_zone = workout_data.get("target_zone")
                if target_zone:
                    return target_zone

                # Try pace_labels
                pace_labels = workout_data.get("pace_labels", {})
                if pace_labels:
                    primary = pace_labels.get("primary", "")
                    if primary:
                        return primary
                    secondary = pace_labels.get("secondary", "")
                    if secondary:
                        return secondary

                # Try extracting from segments (get pace range from first step)
                segments_data = workout_data.get("segments", {})
                if segments_data:
                    normalized_seg = normalize_segments(segments_data)
                    if normalized_seg and isinstance(normalized_seg, dict):
                        steps = normalized_seg.get("steps", [])
                        if steps and isinstance(steps, list) and len(steps) > 0:
                            first_step = steps[0]
                            target = first_step.get("target", {})
                            if isinstance(target, dict):
                                pace_min = target.get("paceMin")
                                pace_max = target.get("paceMax")
                                if pace_min and pace_max:
                                    # Convert seconds per mile to MM:SS format
                                    def sec_to_pace(sec):
                                        mins = int(sec // 60)
                                        secs = int(sec % 60)
                                        return f"{mins}:{secs:02d}"

                                    return f"{sec_to_pace(pace_min)}—{sec_to_pace(pace_max)}/mi"

                return ""

            new_target_zone = extract_pace_zone_string(workout_data)

            if old_target_zone != new_target_zone:
                changes.append(
                    {
                        "field": "Target Pace Zone",
                        "before": old_target_zone or "Not set",
                        "after": new_target_zone or "Not set",
                    }
                )

            # Compare distance/miles
            old_miles = db_workout.miles or 0
            new_miles = workout_data.get("miles") or workout_data.get("distance_mi", 0)
            if abs(old_miles - new_miles) > 0.01:  # Account for floating point
                changes.append(
                    {
                        "field": "Distance",
                        "before": f"{old_miles:.1f} miles",
                        "after": f"{new_miles:.1f} miles",
                    }
                )

            # Compare pace/target zones if available
            old_target_hr = db_workout.target_hr
            new_target_hr = workout_data.get("target_hr")
            if old_target_hr != new_target_hr:
                changes.append(
                    {
                        "field": "Target HR",
                        "before": old_target_hr or "Not set",
                        "after": new_target_hr or "Not set",
                    }
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

        return {
            "week_number": week_num,
            "phase": phase,
            "workouts": week_with_details["workouts"],
            "pace_adjusted": previous_week_logs is not None,
            "quality_disabled": disable_quality,
            "pace_labels": pace_labels,
            "workout_changes": workout_changes,  # Include changes for email
        }


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
    target_week_start = race_date - timedelta(weeks=weeks_before_race)
    days_since_monday = target_week_start.weekday()
    week_start = target_week_start - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)

    # Find workouts in that date range
    week_workouts = [w for w in all_workouts if week_start <= w.date <= week_end]

    return week_workouts


def _date_to_day_name(d: date) -> str:
    """Convert date to day name (Mon, Tue, etc.)."""
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return day_names[d.weekday()]


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
    import json

    # Collect pace targets from workout segments
    easy_paces = []
    steady_paces = []
    marathon_paces = []
    threshold_paces = []

    for workout in workouts:
        if not workout.segments:
            continue

        # Handle both dict format and array format
        segments = workout.segments
        if isinstance(segments, str):
            try:
                segments = json.loads(segments)
            except (json.JSONDecodeError, TypeError):
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
