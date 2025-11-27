"""
Layer 6: Plan Storage Service

Purpose:
    Save validated training plan to database.
    Handle plan record creation, workout insertion, and plan activation.

Responsibilities:
    - Create Plan record in database
    - Create PlanWorkout records (batch insert)
    - Deactivate previous active plans
    - Handle database transactions and rollback

Dependencies:
    - Validated plan from Layer 5 (PlanValidationService)
    - Database models (Plan, PlanWorkout)
    - SQLAlchemy session

Testing:
    See tests/services/training_plan/test_plan_storage_service.py

Author: SmartCoach Development Team
Last Updated: January 2026
"""

import logging
from uuid import UUID
from typing import Dict, Any, List
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from src.db.dao.plans_dao import create_plan
from src.db.dao.plan_workouts_dao import insert_batch
from src.db.dao.user_profile_dao import get_user_profile
from src.db.models.plans import Plan
from src.services.training_plan.workout_detail_rules import (
    INTENSITY_MAP,
    FOCUS_TAGS,
    SEGMENT_SUM_TOLERANCE,
    QUALITY_ENABLED_PHASES,
)
from src.services.training_plan.pace_seed_service import PaceSeed
from src.services.training_plan.workout_types import TYPE_DISPLAY
from src.services.training_plan.workout_utils import pace_range_to_str

logger = logging.getLogger(__name__)

# Import centralized day name utilities
from src.utils.date_helpers import DAY_TO_WEEKDAY, DAY_NAMES_FULL


class PlanStorageService:
    """Service for storing training plans in the database."""

    @staticmethod
    def save_validated_plan(
        session: Session,
        user_id: str,
        validated_plan: Dict[str, Any],
        plan_request: Dict[str, Any],
    ) -> int:
        """
        Save validated training plan to database.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user
            validated_plan: Validated plan from Layer 5 (must have "validated_plan" key)
            plan_request: Original plan request with race details

        Returns:
            plan_id: ID of created plan

        Raises:
            ValueError: If plan is invalid or data is missing
            Exception: Database errors (transaction will be rolled back)
        """
        logger.info(f"Saving validated plan for user {user_id}")

        try:
            # Extract validated plan (Layer 5 returns {"validated_plan": ...})
            if "validated_plan" in validated_plan:
                plan_data = validated_plan["validated_plan"]
            else:
                plan_data = validated_plan  # Assume already validated

            # Parse race date
            race_date_str = plan_request.get("race_date")
            if not race_date_str:
                raise ValueError("race_date is required in plan_request")

            if isinstance(race_date_str, str):
                race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
            elif isinstance(race_date_str, date):
                race_date = race_date_str
            else:
                raise ValueError(f"Invalid race_date format: {race_date_str}")

            # Convert user_id to UUID if string
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            # Prepare plan record
            plan_dict = {
                "user_id": user_uuid,
                "plan_name": plan_data.get("plan_name", f"Marathon Plan - {race_date}"),
                "race_date": race_date,
                "race_distance": plan_request.get("race_distance", "Marathon"),
                "race_name": plan_request.get("race_name"),
                "race_location": plan_request.get("race_location"),
                "race_metadata": plan_request.get("race_metadata"),
                "primary_goal": plan_request.get("primary_goal"),
                "target_time": plan_request.get("target_time"),
                "training_days": plan_request.get("training_days"),
                "notes": plan_request.get("notes"),
                "is_active": True,
            }

            # Deactivate existing active plans
            session.query(Plan).filter_by(user_id=user_uuid, is_active=True).update(
                {"is_active": False}
            )

            # Create plan record
            plan = create_plan(session, plan_dict)
            session.flush()  # Get plan.id
            plan_id = plan.id

            logger.debug(f"Created plan record {plan_id}")

            # Fetch user profile for HR zone calculation
            user_profile = get_user_profile(session, user_id)

            # Convert weeks/workouts to dated workout records
            workouts_to_insert = PlanStorageService._convert_workouts_to_db_format(
                plan_id, plan_data, race_date, user_profile
            )

            if workouts_to_insert:
                # Insert workouts in batch
                insert_batch(session, workouts_to_insert)
                logger.info(
                    f"Saved {len(workouts_to_insert)} workouts for plan {plan_id}"
                )

            # Commit transaction
            session.commit()
            logger.info(f"Successfully saved plan {plan_id} for user {user_id}")

            return plan_id

        except Exception as e:
            session.rollback()
            logger.error(f"Error saving plan for user {user_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def _convert_workouts_to_db_format(
        plan_id: int,
        plan_data: Dict[str, Any],
        race_date: date,
        user_profile: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convert plan weeks/workouts structure to dated workout records.

        Args:
            plan_id: ID of the plan
            plan_data: Plan data with weeks array
            race_date: Race date to calculate workout dates from

        Returns:
            List of workout dictionaries ready for database insertion
        """
        workouts_to_insert = []
        weeks = plan_data.get("weeks", [])

        if not weeks:
            logger.warning("Plan has no weeks - no workouts to save")
            return workouts_to_insert

        # Sort weeks by week_number
        sorted_weeks = sorted(weeks, key=lambda w: w.get("week_number", 0))

        if not sorted_weeks:
            return workouts_to_insert

        max_week_num = max(w.get("week_number", 0) for w in sorted_weeks)

        for week in sorted_weeks:
            week_num = week.get("week_number", 0)
            week_workouts = week.get("workouts", [])

            # Calculate week start date: work backwards from race date
            # Week N should be N weeks before race (approximately)
            # So week 1 is ~(max_week_num - 1) weeks before race
            weeks_before_race = max_week_num - week_num
            week_start = race_date - timedelta(weeks=weeks_before_race)

            # Adjust to Monday of that week
            from src.utils.date_helpers import get_week_start_for_date

            week_start_monday = get_week_start_for_date(week_start)

            # Extract phase and seed from week
            phase = week.get("phase", "Base")

            for workout in week_workouts:
                day_name = workout.get("day", DAY_NAMES_FULL[0])  # Default to Monday
                weekday = DAY_TO_WEEKDAY.get(day_name, 0)  # Default to Monday

                # Calculate workout date
                workout_date = week_start_monday + timedelta(days=weekday)

                # Validate and extract distance
                distance_miles = float(
                    workout.get("miles", workout.get("distance_miles", 0.0)) or 0
                )
                if distance_miles < 0:
                    raise ValueError(
                        f"Invalid distance_miles: {distance_miles} (must be non-negative)"
                    )

                # Extract workout details
                run_type_key = workout.get("type", "easy")
                segments = workout.get("segments", {})
                details = {
                    "segments": segments,
                    "cues": workout.get("cues", ""),
                    "quality_insert": workout.get("quality_insert"),
                }

                # Extract seed from week metadata (stored by Pass4)
                seed_dict = week.get("_pace_seed")
                if not seed_dict:
                    logger.warning(
                        f"Week {week_num}: No pace seed metadata, using defaults"
                    )
                    seed_dict = {
                        "E_min": 600.0,
                        "E_max": 690.0,
                        "S_min": 570.0,
                        "S_max": 630.0,
                        "M": 540.0,
                        "T_min": 510.0,
                        "T_max": 520.0,
                        "week1_long_cap": 8.0,
                    }

                seed = PaceSeed(
                    E_min=seed_dict["E_min"],
                    E_max=seed_dict["E_max"],
                    S_min=seed_dict["S_min"],
                    S_max=seed_dict["S_max"],
                    M=seed_dict["M"],
                    T_min=seed_dict["T_min"],
                    T_max=seed_dict["T_max"],
                    week1_long_cap=seed_dict.get("week1_long_cap", 8.0),
                )

                # Build run dict
                run = {
                    "type": run_type_key,
                    "label": workout.get("label")
                    or workout.get("workout_type")
                    or TYPE_DISPLAY.get(run_type_key, "Easy Run"),
                    "miles": distance_miles,
                }

                # Convert to database row using new mapper
                workout_db = PlanStorageService._workout_to_row(
                    plan_id=plan_id,
                    date=workout_date,
                    phase=phase,
                    run=run,
                    seed=seed,
                    details=details,
                    user_profile=user_profile,
                )

                # Validate before adding
                PlanStorageService._validate_row(workout_db)

                workouts_to_insert.append(workout_db)

        return workouts_to_insert

    @staticmethod
    def _main_step(segments: dict) -> dict:
        """Extract the longest distance step as 'main' segment."""
        steps = (segments or {}).get("steps", [])
        if not steps:
            return {}
        return max(steps, key=lambda s: s.get("value", 0), default={})

    @staticmethod
    def _pace_string_from_target(t: dict) -> str:
        """Convert target dict {low: sec, high: sec} to pace string."""
        if not t:
            return ""
        low = t.get("low")
        high = t.get("high")
        if low is None or high is None:
            return ""
        # Use centralized pace_range_to_str utility
        return pace_range_to_str(low, high)

    @staticmethod
    def _has_marathon_finish(segments: dict) -> bool:
        """Check if segments include a marathon finish step."""
        for s in segments.get("steps", []):
            name_lower = s.get("name", "").lower()
            if name_lower.startswith("marathon") or s.get("intensity") == "MARATHON":
                return True
        return False

    @staticmethod
    def _calculate_hr_zone(
        run_type_key: str, user_profile: Dict[str, Any] = None
    ) -> str:
        """
        Calculate HR zone string (e.g., "Z2 (120-150 bpm)") from workout type.

        Args:
            run_type_key: Workout type key (easy, steady, long, etc.)
            user_profile: User profile dict with max_hr or age_group

        Returns:
            HR zone string like "Z2 (120-150 bpm)" or empty string if can't calculate
        """
        # Standard Strava HR zones (as percentages)
        hr_zones = {
            "Z1": (0.50, 0.60),  # Recovery
            "Z2": (0.60, 0.75),  # Easy/Aerobic
            "Z3": (0.75, 0.85),  # Threshold
            "Z4": (0.85, 0.95),  # VO2 Max
            "Z5": (0.95, 1.00),  # Neuromuscular
        }

        # Map workout type to HR zone based on training philosophy
        # Reference: workout_types.py - INTENSITY_ZONE definitions
        # EASY: "E" -> Z1-Z2 (recovery/easy aerobic)
        # STEADY: "E/steady" -> Z2 (aerobic steady, not hard)
        # ENDURANCE: "E→steady" -> Z2 (easy transitioning to steady)
        # LONG: "E" -> Z2 (easy aerobic)
        # THRESHOLD/TEMPO: -> Z3 (threshold pace)
        # VO2/INTERVALS: -> Z4 (hard intervals)
        run_type_lower = run_type_key.lower()
        if run_type_lower in ["threshold", "tempo"]:
            zone_key = "Z3"  # Threshold pace (75-85% max HR)
        elif run_type_lower in ["vo2", "intervals", "repetitions", "race"]:
            zone_key = "Z4"  # VO2 max intervals (85-95% max HR)
        elif run_type_lower in ["steady"]:
            zone_key = "Z2"  # Aerobic steady (60-75% max HR) - controlled, not hard
        elif run_type_lower in ["long", "endurance"]:
            zone_key = "Z2"  # Easy/steady aerobic (60-75% max HR)
        else:  # easy, recovery, or default
            zone_key = "Z2"  # Easy aerobic (60-75% max HR)

        # Get max HR from user profile or estimate
        max_hr = None
        if user_profile:
            max_hr = user_profile.get("max_hr")
            if not max_hr or max_hr == 0:
                # Try to estimate from age_group
                age_group = user_profile.get("age_group", "")
                if age_group:
                    # Extract age from age_group (e.g., "30-39" -> 35)
                    try:
                        if "-" in str(age_group):
                            age_range = str(age_group).split("-")
                            age = (int(age_range[0]) + int(age_range[1])) // 2
                        else:
                            age = int(str(age_group).replace("+", "").split("-")[0])
                        max_hr = 220 - age
                    except (ValueError, IndexError):
                        pass

        # Default max HR if still not available
        if not max_hr or max_hr == 0:
            max_hr = 190  # Conservative default

        # Calculate HR range
        hr_lo, hr_hi = hr_zones[zone_key]
        hr_min = int(hr_lo * max_hr)
        hr_max = int(hr_hi * max_hr)

        return f"{zone_key} ({hr_min}–{hr_max} bpm)"

    @staticmethod
    def _workout_to_row(
        plan_id: int,
        date: date,
        phase: str,
        run: dict,
        seed: PaceSeed,
        details: dict,
        user_profile: Dict[str, Any] = None,
    ) -> dict:
        """
        Convert workout data to database row format.

        Now reads seed directly (no reconstruction).
        """
        run_type_key = run.get("type", "easy")
        segments = details.get("segments", {})
        main = PlanStorageService._main_step(segments)
        target_zone = PlanStorageService._pace_string_from_target(
            main.get("target", {})
        )

        # Determine intensity from config
        intensity = INTENSITY_MAP.get(run_type_key, "E")
        if run_type_key == "long" and PlanStorageService._has_marathon_finish(segments):
            intensity = "M"  # Long run with M finish

        # Build pace_ranges from seed (integer seconds)
        pace_ranges = {
            "E": [int(seed.E_min), int(seed.E_max)],
            "S": [int(seed.S_min), int(seed.S_max)],
            "M": [int(seed.M), int(seed.M)],
            "T": [int(seed.T_min), int(seed.T_max)],
        }

        # Get workout label
        workout_label = run.get("label") or TYPE_DISPLAY.get(run_type_key, "Easy Run")

        # Calculate HR zone
        target_hr = PlanStorageService._calculate_hr_zone(run_type_key, user_profile)

        return {
            "plan_id": plan_id,
            "date": date,
            "workout_type": workout_label,
            "run_type_key": run_type_key,
            "phase": phase,
            "miles": run.get("miles", 0.0),
            "intensity": intensity,
            "target_zone": target_zone,
            "target_hr": target_hr,
            "focus": FOCUS_TAGS.get(run_type_key, "Run"),
            "description": details.get("cues", ""),
            "cues": details.get("cues", ""),
            "pace_ranges": pace_ranges,
            "allow_quality": (phase in QUALITY_ENABLED_PHASES),
            "quality_insert": details.get("quality_insert"),
            "segments": segments,  # ✅ Spec-compliant segments
        }

    @staticmethod
    def _validate_row(row: dict):
        """Validate workout row before insertion."""
        seg = row.get("segments") or {}
        steps = seg.get("steps") or []

        if steps:
            # Sum of step distances should equal miles
            tot = sum(
                s.get("value", 0) for s in steps if s.get("durationType") == "DISTANCE"
            )
            miles = row.get("miles", 0)
            if abs(tot - miles) >= SEGMENT_SUM_TOLERANCE:
                raise ValueError(
                    f"Segments total ({tot:.2f}) != miles ({miles:.2f}), "
                    f"diff: {abs(tot - miles):.2f}"
                )

            # Validate target bounds
            for s in steps:
                t = s.get("target")
                if t:
                    low = t.get("low", 0)
                    high = t.get("high", 0)
                    if low > high:
                        raise ValueError(
                            f"Bad target bounds in step '{s.get('name')}': "
                            f"low={low} > high={high}"
                        )

        # Validate run_type_key
        run_type_key = row.get("run_type_key")
        if run_type_key not in (
            "easy",
            "steady",
            "endurance",
            "long",
            "long_run",
            "tempo",
            "intervals",
            "hills",
            "recovery",
            "threshold",
            "fartlek",
            "race",
            "Race",
            "shakeout",
        ):
            raise ValueError(f"Invalid run_type_key: {run_type_key}")

    @staticmethod
    def save_plan(
        session: Session, user_id: str, validated_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Alias for save_validated_plan (backwards compatibility).

        Note: This method signature doesn't include plan_request, so it attempts
        to extract race details from validated_plan. For new code, use save_validated_plan.
        """
        # Extract plan_request from validated_plan if possible
        plan_data = validated_plan.get("validated_plan", validated_plan)
        weeks = plan_data.get("weeks", [])

        # Estimate race date from weeks (not ideal, but works for compatibility)
        num_weeks = len(weeks) if weeks else 16
        estimated_race_date = (datetime.now() + timedelta(weeks=num_weeks)).strftime(
            "%Y-%m-%d"
        )

        plan_request = {
            "race_date": estimated_race_date,
            "primary_goal": "Just Finish",
        }

        plan_id = PlanStorageService.save_validated_plan(
            session, user_id, validated_plan, plan_request
        )

        return {
            "plan_id": plan_id,
            "workouts_created": (
                len(plan_data.get("weeks", [{}])[0].get("workouts", []))
                if plan_data.get("weeks")
                else 0
            ),
            "status": "SUCCESS",
        }
