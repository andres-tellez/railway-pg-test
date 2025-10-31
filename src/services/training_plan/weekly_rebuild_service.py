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
        if initial_seed is None:
            # Get Week 1 totals to seed pace
            first_week_workouts = (
                all_workouts[:7] if len(all_workouts) >= 7 else all_workouts
            )  # Approximate
            week1_total = sum(w.miles for w in first_week_workouts[:7])
            week1_long = max(
                (
                    w.miles
                    for w in first_week_workouts
                    if w.workout_type in ("Long Run", "long")
                ),
                default=8.0,
            )

            # Fetch Strava activities for pace seeding (reuse existing infrastructure)
            from src.services.training_plan.data_collection_service import (
                DataCollectionService,
            )

            raw_data = DataCollectionService.collect_all_data(
                session=session,
                user_id=str(plan.user_id),
                plan_request={},  # Minimal plan request for weekly rebuild
                activity_weeks=12,
            )
            strava_activities = raw_data.get("strava_activities", [])

            initial_seed = get_initial_pace_seed(
                strava_activities=strava_activities,
                plan_week1_total=week1_total,
                plan_week1_long=week1_long,
                goal_mp_sec_per_mi=None,
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
        pass4 = Pass4WorkoutDetails()
        allow_quality = (phase in ("Build", "Peak")) and not disable_quality

        week_with_details = pass4.add_details_to_week(
            week=week_plan,
            seed=current_seed,
            allow_quality=allow_quality,
        )

        # Update workouts in database
        updated_count = 0
        for workout_data, db_workout in zip(
            week_with_details["workouts"], week_workouts
        ):
            # Update segments and related fields
            segments = workout_data.get("segments", [])
            cues = workout_data.get("cues", "")
            pace_labels = workout_data.get("pace_labels", {})

            update_data = {
                "segments": segments,  # Store as JSON
                "description": cues,  # Update description with cues
                "intensity": workout_data.get(
                    "type", db_workout.workout_type
                ),  # May update intensity
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
