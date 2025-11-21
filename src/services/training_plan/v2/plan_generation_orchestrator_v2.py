"""
Plan Generation Orchestrator V2

Wires together the race-distance-aware services (Pass1, weekly totals, Pass3, Pass4,
recovery insertion, validation) to produce a deterministic draft plan.
"""

from typing import Any, Dict, List, Optional
import logging
from datetime import datetime, date, timedelta

from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.shared_v2.data_collection_service_v2 import (
    DataCollectionService as DataCollectionServiceV2,
)
from src.services.training_plan.v2.shared_v2.insights_calculation_service_v2 import (
    InsightsCalculationService as InsightsCalculationServiceV2,
)
from src.services.training_plan.v2.marathon.pass1_longrun_first_v2 import (
    Pass1LongRunFirstV2,
)
from src.services.training_plan.v2.marathon.weekly_total_calculator_v2 import (
    calculate_weekly_totals_from_long_runs,
)
from src.services.training_plan.v2.pass3_workout_distribution_v2 import (
    Pass3WorkoutDistribution,
)
from src.services.training_plan.v2.pass4_workout_details_v2 import Pass4WorkoutDetails
from src.services.training_plan.v2.plan_validation_service_v2 import (
    PlanValidationServiceV2,
)
from src.services.training_plan.v2.recovery_week_insertion_service_v2 import (
    apply_recovery_week_insertion_if_needed,
)
from src.services.training_plan.v2.shared_v2.pace_seed_service import (
    get_initial_pace_seed,
    PaceSeed,
)
from src.services.training_plan.v2.shared_v2.pass1_weeks_selector_v2 import (
    Pass1WeeksSelector as Pass1WeeksSelectorV2,
)
from src.utils.date_helpers import get_week_start_for_date
from src.services.training_plan.v2.marathon.workout_types_v2 import (
    EASY,
    TYPE_DISPLAY,
    PACE_GUIDANCE,
)

logger = logging.getLogger(__name__)


class PlanGenerationOrchestratorV2:
    """
    Race-distance-aware orchestrator for the long-run-first deterministic pipeline.
    """

    def __init__(self, config: RaceDistanceConfig) -> None:
        self.config = config
        self.data_collector = DataCollectionServiceV2()
        self.insights_service = InsightsCalculationServiceV2()

        self.pass1 = Pass1LongRunFirstV2(
            config=config,
            data_collector=self.data_collector,
            insights_service=self.insights_service,
        )
        self.pass3 = Pass3WorkoutDistribution(config=config)
        self.pass4 = Pass4WorkoutDetails()
        self.validator = PlanValidationServiceV2(config=config)
        self.pass1_selector = Pass1WeeksSelectorV2(
            data_collector=self.data_collector,
            insights_service=self.insights_service,
        )

    def generate_longrun_first(
        self,
        runner_ctx: Dict[str, Any],
        mode: str = "prefill",
        week_logs: Optional[Dict[int, List]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the LR-first pipeline and return validation results.

        Args:
            runner_ctx: Dict with session, user_id, plan_request, training_days, etc.
            mode: "prefill" (default) or "rolling".
            week_logs: optional logs for Pass4 adjustments (rolling mode).
        """
        session = runner_ctx.get("session")
        user_id = runner_ctx.get("user_id")
        plan_request = runner_ctx.get("plan_request", {})
        training_days = runner_ctx.get("training_days")

        if not session or not user_id:
            return {
                "valid": False,
                "violations": [
                    {
                        "rule": "context_missing",
                        "severity": "error",
                        "details": "session and user_id required",
                    }
                ],
                "draft": {},
            }

        if not training_days:
            from src.utils.date_helpers import DEFAULT_TRAINING_DAYS

            training_days = DEFAULT_TRAINING_DAYS

        runs_per_week = len(training_days)

        # Note: Max HR sync from Strava is not available - Strava API doesn't return max_heartrate
        # Users must enter max HR manually in their profile

        # Pass 1 Weeks selector for recommended plan length
        lr_output = self.pass1.build(
            session=session,
            user_id=str(user_id),
            plan_request=plan_request,
            activity_weeks=runner_ctx.get("activity_weeks", 12),
        )
        weeks_long = lr_output.get("weeks", [])

        # Weekly totals from long runs
        weeks_with_totals = calculate_weekly_totals_from_long_runs(
            weeks=weeks_long,
            runs_per_week=runs_per_week,
            config=self.config,
        )

        # Pass3 distribution
        pass3_plan = self.pass3.run(
            weeks_with_totals,
            training_days,
        )

        weeks_out = pass3_plan.get("weeks", [])

        # Recovery week insertion if plan shorter than available time
        race_date = plan_request.get("race_date")
        start_date = plan_request.get("start_date")

        weeks_after_recovery, recovery_meta = apply_recovery_week_insertion_if_needed(
            weeks_out,
            race_date,
            config=self.config,
            plan_start_date=start_date,
            timezone_str=plan_request.get("user_timezone", "UTC"),
        )

        if recovery_meta.get("inserted"):
            # Re-run Pass3 workout distribution for inserted weeks
            # First, recalc weekly totals for new weeks (they already have weekly_mileage)
            pass3_plan = self.pass3.run(weeks_after_recovery, training_days)
            weeks_out = pass3_plan.get("weeks", [])

        weeks_out = self._append_race_week(weeks_out)

        aligned_start_date = self._compute_aligned_start_date(
            race_date=race_date,
            weeks_count=len(weeks_out),
            fallback_start=start_date,
        )
        if aligned_start_date:
            current = aligned_start_date
            for week in weeks_out:
                week["week_start_date"] = current.isoformat()
                week["week_label"] = current.strftime("%Y-%m-%d")
                current += timedelta(days=7)
            plan_request["start_date"] = aligned_start_date.isoformat()

        # Pace seed (use collected data via Pass1)
        pace_seed = self._derive_pace_seed(lr_output, plan_request, weeks_out)

        # Pass4 - add workout details
        plan_with_details = {
            "weeks": weeks_out,
            "start_date": plan_request.get("start_date"),
            "race_date": race_date,
        }
        plan_with_details = self.pass4.add_details_to_plan(
            plan=plan_with_details,
            seed=pace_seed,
            mode=mode,
            week_logs=week_logs or {},
        )

        validation = self.validator.validate_plan(plan_with_details)
        validation["draft"] = plan_with_details
        validation["recovery_metadata"] = recovery_meta
        validation["pass1_rationale"] = lr_output.get("rationale")
        return validation

    @staticmethod
    def _parse_date_like(value: Any) -> Optional[date]:
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        try:
            return datetime.fromisoformat(str(value).split("T")[0]).date()
        except Exception:
            return None

    def _compute_aligned_start_date(
        self, *, race_date: Any, weeks_count: int, fallback_start: Any
    ) -> Optional[date]:
        """
        Compute start date for plan, ensuring it's never in the past.

        Priority:
        1. If race_date provided: Calculate backwards from race date (for alignment)
        2. Ensure minimum start is the week AFTER current week (no past dates)
        3. Fallback to provided start_date if available
        4. Default to next Monday if all else fails

        This ensures plans always start in the future, regardless of marathon date.
        """
        if weeks_count <= 0:
            return self._parse_date_like(fallback_start)

        # Calculate minimum start date: week AFTER current week (next Monday)
        from src.utils.date_helpers import get_current_week_start, get_next_monday

        today = datetime.now().date()
        current_week_start = get_current_week_start()
        # Get Monday of the week AFTER current week (next Monday)
        min_start_date = get_next_monday(today, include_today=False)

        calculated_start = None

        if race_date:
            try:
                race_week_start = get_week_start_for_date(race_date)
                offset_weeks = max(0, weeks_count - 1)
                calculated_start = race_week_start - timedelta(weeks=offset_weeks)
                logger.info(
                    f"Calculated start from race date: {calculated_start} "
                    f"(race_week_start={race_week_start}, weeks_count={weeks_count})"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to align start date from race_date={race_date}: {e}"
                )

        # Use calculated start if available, otherwise try fallback
        if calculated_start:
            start_date = calculated_start
        else:
            parsed_fallback = self._parse_date_like(fallback_start)
            if parsed_fallback:
                start_date = parsed_fallback
            else:
                # Default to next Monday
                start_date = min_start_date

        # CRITICAL: Ensure start date is never in the past
        # Use the later of: calculated/fallback start OR minimum (next Monday)
        if start_date < min_start_date:
            logger.warning(
                f"Start date {start_date} is in the past. "
                f"Adjusting to minimum start date: {min_start_date} (week after current week)"
            )
            start_date = min_start_date

        logger.info(
            f"Final aligned start date: {start_date} "
            f"(min_start={min_start_date}, calculated={calculated_start})"
        )
        return start_date

    def _append_race_week(self, weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not weeks:
            return weeks

        template = self.config.race_week_template()
        race_week = {
            "week_number": len(weeks) + 1,
            "phase": template.get("phase", "Race Week"),
            "weekly_mileage": template.get("weekly_mileage", 0),
            "long_run_miles": template.get("long_run_miles", 0),
            "workouts": [
                self._build_race_week_workout(workout_spec)
                for workout_spec in template.get("workouts", [])
            ],
        }
        weeks.append(race_week)
        return weeks

    @staticmethod
    def _easy_workout(
        day: str,
        miles: float,
        *,
        note: str | None = None,
        shakeout: bool = False,
    ) -> Dict[str, Any]:
        workout = {
            "day": day,
            "type": EASY,
            "workout_type": TYPE_DISPLAY[EASY],
            "label": "Shakeout" if shakeout else TYPE_DISPLAY[EASY],
            "miles": miles,
            "distance_miles": miles,
            "pace_guidance": PACE_GUIDANCE[EASY],
        }
        if note:
            workout["notes"] = note
        return workout

    def _build_race_week_workout(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        kind = str(spec.get("kind", "easy")).lower()
        day = spec.get("day") or "Mon"
        miles = float(spec.get("miles", 0) or 0)
        note = spec.get("note")
        if kind == "race":
            race_distance = miles or self.config.race_distance_miles
            return {
                "day": day,
                "type": "Race",
                "workout_type": spec.get("workout_type", "Race Day"),
                "label": spec.get("label", "Race Day"),
                "miles": race_distance,
                "distance_miles": race_distance,
                "pace_guidance": spec.get("pace_guidance", "Celebrate"),
                "notes": note,
            }
        return self._easy_workout(
            day, miles, note=note, shakeout=bool(spec.get("shakeout"))
        )

    def _derive_pace_seed(
        self,
        lr_output: Dict[str, Any],
        plan_request: Dict[str, Any],
        weeks_out: List[Dict[str, Any]],
    ) -> PaceSeed:
        """Create an initial pace seed using the raw data from Pass1."""
        # Reuse data collected in Pass1 (if stored) or fallback
        week1 = weeks_out[0] if weeks_out else {}
        week1_total = float(week1.get("weekly_mileage", 0) or 0)
        week1_long = float(week1.get("long_run_miles", 0) or 0)

        # If Pass1 stored raw data, use it; otherwise, we only have plan_request
        strava_activities = lr_output.get("strava_activities", [])

        seed = get_initial_pace_seed(
            strava_activities=strava_activities,
            plan_week1_total=week1_total,
            plan_week1_long=week1_long,
            goal_mp_sec_per_mi=None,
        )
        return seed
