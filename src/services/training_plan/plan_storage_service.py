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
    - Validated plan from ``PlanValidationServiceV2`` (orchestrator / v2 pipeline)
    - Database models (Plan, PlanWorkout)
    - SQLAlchemy session

Testing:
    See tests/services/training_plan/test_plan_storage_service.py

Author: SmartCoach Development Team
Last Updated: January 2026
"""

import logging
from uuid import UUID
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session

from src.db.dao.plans_dao import create_plan
from src.db.dao.plan_workouts_dao import insert_batch
from src.db.dao.user_profile_dao import get_user_profile
from src.db.models.plans import Plan
from src.services.training_plan.workout_detail_rules import (
    QUALITY_ENABLED_PHASES,
    SEGMENT_SUM_TOLERANCE,
)
from src.services.training_plan.workout_utils import pace_range_to_str
from src.smartcoach_mobile_coach.runner_profile import (
    get_runner_pace_band_for_run_type,
    get_runner_pace_zone_key_for_run_type,
    get_runner_zone_string_for_run_type,
    placement_focus_tag,
    resolve_taxonomy_and_placement,
    runner_pace_ranges_payload,
    validate_persisted_run_type_key,
    workout_display_label,
)

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
        context_snapshot: Any = None,
    ) -> int:
        """
        Save validated training plan to database.

        Args:
            session: SQLAlchemy database session
            user_id: UUID string of the user
            validated_plan: Validated plan from Layer 5 (must have "validated_plan" key)
            plan_request: Original plan request with race details
            context_snapshot: Optional JSON-serializable reasoning snapshot; when ``None``,
                ``plans.context_snapshot`` is left unset (NULL).

        Returns:
            plan_id: ID of created plan

        Raises:
            ValueError: If plan is invalid or data is missing
            Exception: Database errors (transaction will be rolled back)
        """
        print("SNAPSHOT IN STORAGE:", context_snapshot is not None)
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
            # Use custom plan_name from request, or generate smart default
            custom_plan_name = plan_request.get("plan_name")
            race_name = plan_request.get("race_name")
            race_distance = plan_request.get("race_distance", "Marathon")
            training_days = plan_request.get("training_days", [])
            days_count = len(training_days) if training_days else 0

            if custom_plan_name:
                final_plan_name = custom_plan_name
            elif race_name and days_count:
                final_plan_name = f"{race_name} - {days_count} day plan"
            elif race_name:
                final_plan_name = f"{race_name} Training Plan"
            elif days_count:
                final_plan_name = f"{race_distance} {days_count}-day Plan - {race_date}"
            else:
                final_plan_name = f"{race_distance} Plan - {race_date}"

            plan_dict = {
                "user_id": user_uuid,
                "plan_name": final_plan_name,
                "race_date": race_date,
                "race_distance": race_distance,
                "race_name": race_name,
                "race_location": plan_request.get("race_location"),
                "race_metadata": plan_request.get("race_metadata"),
                "primary_goal": plan_request.get("primary_goal"),
                "target_time": plan_request.get("target_time"),
                "training_days": plan_request.get("training_days"),
                "notes": plan_request.get("notes"),
                "is_active": True,
            }
            if context_snapshot is not None:
                from src.services.training_plan.v2.json_utils import make_json_safe

                context_snapshot = make_json_safe(context_snapshot)
                plan_dict["context_snapshot"] = context_snapshot

            # Deactivate existing active plans
            session.query(Plan).filter_by(user_id=user_uuid, is_active=True).update(
                {"is_active": False}
            )

            # Create plan record
            plan = create_plan(session, plan_dict)
            session.flush()  # Get plan.id
            plan_id = plan.id

            if context_snapshot is not None:
                plan.context_snapshot = context_snapshot

            logger.debug(f"Created plan record {plan_id}")

            # Fetch user profile for HR zone calculation
            user_profile = get_user_profile(session, user_id)

            # Convert weeks/workouts to dated workout records
            workouts_to_insert = PlanStorageService._convert_workouts_to_db_format(
                plan_id,
                plan_data,
                race_date,
                user_profile,
                session=session,
                user_id=user_id,
            )

            if workouts_to_insert:
                # Insert workouts in batch
                insert_batch(session, workouts_to_insert)
                logger.info(
                    f"Saved {len(workouts_to_insert)} workouts for plan {plan_id}"
                )

            # Commit transaction (plans_dao.create_plan only flushes; commit happens here)
            try:
                session.commit()
            except Exception as e:
                print("DB COMMIT ERROR:", repr(e))
                raise

            try:
                from src.smartcoach_mobile_coach.runner_profile import (
                    refresh_runner_profile,
                )

                refresh_runner_profile(session, user_id)
            except Exception as e:
                logger.warning(
                    "runner_zone_profiles refresh failed after plan save (plan_id=%s): %s",
                    plan_id,
                    e,
                )

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
        session: Optional[Session] = None,
        user_id: Optional[str] = None,
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

                # Extract workout details (type may be taxonomy key or placement role)
                raw_type = workout.get("type", "easy")
                taxonomy_type, _placement_role = resolve_taxonomy_and_placement(
                    raw_type
                )
                segments = workout.get("segments", {})
                details = {
                    "segments": segments,
                    "cues": workout.get("cues", ""),
                    "quality_insert": workout.get("quality_insert"),
                }

                # Build run dict
                run = {
                    "type": raw_type,
                    "label": workout.get("label")
                    or workout.get("workout_type")
                    or workout_display_label(taxonomy_type),
                    "miles": distance_miles,
                }

                # Convert to database row using new mapper
                workout_db = PlanStorageService._workout_to_row(
                    plan_id=plan_id,
                    date=workout_date,
                    phase=phase,
                    run=run,
                    details=details,
                    user_profile=user_profile,
                    session=session,
                    user_id=user_id,
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
        run_type_key: str,
        user_profile: Dict[str, Any] = None,
        *,
        session: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        DEPRECATED:
            New reads should consume central runner zone profile data.
            This helper remains for legacy plan row generation compatibility.

        Calculate HR zone display from runner_zone_profiles SoT.

        Args:
            run_type_key: Workout type key (easy, steady, long, etc.)
            user_profile: User profile dict with max_hr, resting_hr, or age_group

        Returns:
            HR zone string like "Z2 (120-150 bpm)" or empty string if can't calculate
        """
        if session is None or user_id is None:
            # Strict SoT mode: no local derivation.
            return ""
        try:
            return get_runner_zone_string_for_run_type(
                session,
                str(user_id),
                run_type_key,
                force_refresh=False,
            )
        except Exception as exc:
            logger.warning(
                "runner profile zone lookup failed for target_hr (%s): %s",
                user_id,
                exc,
            )
            return ""

    @staticmethod
    def _workout_to_row(
        plan_id: int,
        date: date,
        phase: str,
        run: dict,
        details: dict,
        user_profile: Dict[str, Any] = None,
        session: Optional[Session] = None,
        user_id: Optional[str] = None,
    ) -> dict:
        """
        Convert workout data to database row format.

        Now reads seed directly (no reconstruction).
        """
        taxonomy_type, persisted_key = resolve_taxonomy_and_placement(
            run.get("type", "easy"),
            workout_type=run.get("label"),
        )
        segments = details.get("segments", {})
        main = PlanStorageService._main_step(segments)
        target_zone = PlanStorageService._pace_string_from_target(
            main.get("target", {})
        )

        has_marathon_finish = (
            taxonomy_type == "long_run"
            and PlanStorageService._has_marathon_finish(segments)
        )
        intensity = get_runner_pace_zone_key_for_run_type(
            taxonomy_type,
            has_marathon_finish=has_marathon_finish,
        )

        pace_ranges: dict[str, list[int]] = {}
        if session is not None and user_id is not None:
            try:
                from src.smartcoach_mobile_coach.runner_profile import (
                    get_runner_profile,
                )

                profile = get_runner_profile(session, str(user_id))
                pace_ranges = runner_pace_ranges_payload(profile)
                pace_band = get_runner_pace_band_for_run_type(
                    session,
                    str(user_id),
                    taxonomy_type,
                    force_refresh=False,
                )
                if pace_band is not None:
                    target_zone = pace_range_to_str(
                        float(pace_band[0]), float(pace_band[1])
                    )
            except Exception as exc:
                logger.warning(
                    "runner profile pace lookup failed for workout row (%s): %s",
                    user_id,
                    exc,
                )

        workout_label = run.get("label") or workout_display_label(taxonomy_type)

        target_hr = PlanStorageService._calculate_hr_zone(
            taxonomy_type,
            user_profile,
            session=session,
            user_id=user_id,
        )

        return {
            "plan_id": plan_id,
            "date": date,
            "workout_type": workout_label,
            "run_type_key": persisted_key,
            "phase": phase,
            "miles": run.get("miles", 0.0),
            "intensity": intensity,
            "target_zone": target_zone,
            "target_hr": target_hr,
            "focus": placement_focus_tag(taxonomy_type),
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

        # Validate run_type_key (taxonomy keys; matches DB chk_run_type_key)
        run_type_key = row.get("run_type_key")
        if run_type_key is not None:
            row["run_type_key"] = validate_persisted_run_type_key(
                run_type_key,
                workout_type=row.get("workout_type"),
            )

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
