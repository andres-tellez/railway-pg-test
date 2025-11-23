"""
Plan Generation Orchestrator V2

Wires together the race-distance-aware services (Pass1, weekly totals, Pass3, Pass4,
recovery insertion, validation) to produce a deterministic draft plan.
"""

from typing import Any, Dict, List, Optional, Tuple
import logging
from datetime import date, timedelta

from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    validate_phase_quality,
)

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

# Recovery week insertion removed - spine generator now handles all progression naturally
from src.services.training_plan.v2.shared_v2.pace_seed_service import (
    get_initial_pace_seed,
    PaceSeed,
)
from src.services.training_plan.v2.shared_v2.pass1_weeks_selector_v2 import (
    Pass1WeeksSelector as Pass1WeeksSelectorV2,
)
from src.services.training_plan.v2.race_date_validation_service import (
    RaceDateValidationService,
)
from src.services.training_plan.v2.plan_constraints_service import (
    PlanConstraintsService,
)
from src.services.training_plan.v2.marathon.workout_types_v2 import (
    EASY,
    TYPE_DISPLAY,
    PACE_GUIDANCE,
)
from src.services.metrics_helper_service import (
    get_weekly_fitness_from_materialized_view,
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
        self.race_date_validator = RaceDateValidationService()
        self.constraints_service = PlanConstraintsService()

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

        # Note: Max HR must be entered manually in user profile
        # Strava API doesn't return max_heartrate, so manual entry is required

        # Step 0: Validate race date readiness (NEW)
        # This checks if user has sufficient time and base fitness before generating plan
        race_date_validation = None
        race_date = plan_request.get("race_date")
        start_date = plan_request.get("start_date")

        if race_date:
            # Use materialized view for validation to match UI display
            # This ensures the numbers shown to the user match what's used for validation
            # Uses the same calculation as the metrics endpoint
            current_weekly_mileage, current_long_run = (
                get_weekly_fitness_from_materialized_view(
                    session=session, user_id=str(user_id)
                )
            )

            # Fallback to insights calculation if materialized view is not available
            if current_weekly_mileage == 0:
                logger.warning(
                    "Materialized view returned 0 weekly mileage, falling back to insights calculation"
                )
                raw = self.data_collector.collect_all_data(
                    session=session,
                    user_id=user_id,
                    plan_request=plan_request,
                    activity_weeks=runner_ctx.get("activity_weeks", 12),
                )
                insights = self.insights_service.calculate_all_insights(raw)
                current_fitness = insights.get("current_fitness", {})
                current_weekly_mileage = float(
                    current_fitness.get("weekly_mileage", 0) or 0
                )
                current_long_run = float(current_fitness.get("longest_run", 0) or 0)

            race_date_validation = self.race_date_validator.validate(
                race_date=race_date,
                plan_start_date=start_date,
                current_weekly_mileage=current_weekly_mileage,
                current_long_run=current_long_run,
            )

            logger.info(
                f"🎯 Race date validation: status={race_date_validation.get('status')}, "
                f"available={race_date_validation.get('available_weeks')} weeks, "
                f"required={race_date_validation.get('required_weeks')} weeks, "
                f"can_proceed={race_date_validation.get('can_proceed', False)}"
            )

            # Always generate plan and include validation results
            # Frontend will show dialog based on validation status and let user decide
            # Don't block plan generation here - user can still view the plan even if timeline is tight

        # Step 1: Get readiness-based plan length recommendation
        # This uses user's weekly mileage to recommend appropriate plan length
        # Mapping: <15mpw→24w, 15-<20mpw→20w, 20-30mpw→16w, >30mpw→12w
        weeks_recommendation = self.pass1_selector.select_weeks(
            session=session,
            user_id=str(user_id),
            plan_request=plan_request,
            activity_weeks=runner_ctx.get("activity_weeks", 12),
        )
        recommended_weeks = weeks_recommendation.get("weeks")
        rationale = weeks_recommendation.get("rationale", {})
        base_mileage = rationale.get("base_mileage_mpw", 0)
        logger.info(
            f"✅ Readiness-based plan length: {recommended_weeks} weeks "
            f"(weekly_mileage={base_mileage:.1f}mpw, "
            f"longest_run={rationale.get('longest_recent_run_miles', 0):.1f}mi)"
        )

        # Step 1.5: Calculate plan constraints (fitness-based vs race date)
        # Use PlanConstraintsService to centralize constraint logic
        min_start_date = self.constraints_service.get_min_start_date()
        constraints = self.constraints_service.calculate_plan_constraints(
            race_date=race_date,
            recommended_weeks=recommended_weeks,
            min_start_date=min_start_date,
        )

        # Step 2: Build long run progression
        # GUARDRAIL: Pass available_weeks (not target_weeks) to let spine generator
        # handle extra weeks naturally with gradual progression, not post-processing
        # This ensures single source of truth for progression logic
        available_weeks = constraints.available_weeks or constraints.target_weeks
        lr_output = self.pass1.build(
            session=session,
            user_id=str(user_id),
            plan_request=plan_request,
            activity_weeks=runner_ctx.get("activity_weeks", 12),
            recommended_weeks=available_weeks,  # Use available weeks - spine handles progression
        )
        weeks_long = lr_output.get("weeks", [])

        # GUARDRAIL: Validate spine immutability - no modifications after generation
        self._validate_spine_immutability(weeks_long)

        # GUARDRAIL: Validate spine quality - check cutback spacing, progression, etc.
        is_valid, quality_issues = validate_phase_quality(
            weeks_long,
            peak=self.config.target_peak_miles,
            cutback_every=self.config.cutback_every,
            taper_weeks=self.config.taper_weeks,
            taper_ratios=self.config.taper_ratios,
        )

        # Self-correction: Try to fix validation issues automatically
        if not is_valid:
            logger.warning(
                f"Spine quality validation failed: {'; '.join(quality_issues)}. "
                f"Attempting self-correction..."
            )
            corrected_weeks, remaining_issues = self._self_correct_spine(
                weeks_long=weeks_long,
                quality_issues=quality_issues,
                plan_request=plan_request,
                session=session,
                user_id=str(user_id),
                runner_ctx=runner_ctx,
                available_weeks=available_weeks,
                constraints=constraints,
                max_attempts=2,
            )
            weeks_long = corrected_weeks
            quality_issues = remaining_issues

            if remaining_issues:
                logger.error(
                    f"Self-correction completed but {len(remaining_issues)} issues remain: "
                    f"{'; '.join(remaining_issues)}"
                )
                for issue in remaining_issues:
                    logger.error(f"  - {issue}")
            else:
                logger.info("✅ Self-correction successful - all issues resolved")

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

        # GUARDRAIL: No post-processing of spine - progression is calculated once in spine generator
        # If plan needs adjustment, regenerate with different parameters, don't modify

        weeks_out = self._append_race_week(weeks_out)

        # Step 5.5: Calculate start date and trim plan if needed
        # Use PlanConstraintsService for consistent date calculation and trimming
        aligned_start_date = self.constraints_service.calculate_start_date(
            race_date=race_date,
            plan_length_weeks=len(weeks_out),
            min_start_date=min_start_date,
            fallback_start=start_date,
        )

        if aligned_start_date:
            # Trim plan if it exceeds race date constraint
            weeks_out, aligned_start_date = (
                self.constraints_service.trim_plan_to_constraints(
                    weeks=weeks_out,
                    race_date=race_date,
                    start_date=aligned_start_date,
                )
            )

            # Assign dates to weeks
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
        validation["pass1_rationale"] = lr_output.get("rationale")
        # Include race date validation results if available
        if race_date_validation:
            validation["race_date_validation"] = race_date_validation

        # Include spine quality validation results
        # This checks cutback spacing, progression safety, peak achievement, etc.
        validation["spine_quality"] = {
            "is_valid": is_valid,
            "issues": quality_issues,
        }

        return validation

    # NOTE: Date parsing and start date calculation moved to PlanConstraintsService
    # for better separation of concerns and consistency across components

    def _validate_spine_immutability(self, weeks: List[Dict[str, Any]]) -> None:
        """
        GUARDRAIL: Validate that spine hasn't been modified after generation.

        This ensures single source of truth - spine is calculated once and never modified.
        If modifications are needed, regenerate with different parameters.

        Contract:
            - Input: weeks from spine generator
            - Validates: structure, progression, peak reached
            - Side Effects: NONE (read-only validation)
            - Raises: AssertionError if validation fails
        """
        if not weeks:
            raise AssertionError("Spine must have at least one week")

        # Validate structure
        for i, week in enumerate(weeks):
            if "long_run_miles" not in week:
                raise AssertionError(f"Week {i+1} missing long_run_miles")
            if "phase" not in week:
                raise AssertionError(f"Week {i+1} missing phase")
            lr = float(week.get("long_run_miles", 0) or 0)
            if lr <= 0:
                raise AssertionError(f"Week {i+1} has invalid long_run_miles: {lr}")

        # Validate peak is reached (within tolerance)
        max_lr = max(float(w.get("long_run_miles", 0) or 0) for w in weeks)
        peak_target = self.config.target_peak_miles
        if max_lr < peak_target - 1.0:  # Allow 1 mile tolerance
            raise AssertionError(
                f"Spine must reach peak ({peak_target} miles), got max {max_lr:.1f} miles"
            )

        logger.debug(
            f"✅ Spine validation passed: {len(weeks)} weeks, peak {max_lr:.1f} miles"
        )

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

    def _self_correct_spine(
        self,
        weeks_long: List[Dict[str, Any]],
        quality_issues: List[str],
        plan_request: Dict[str, Any],
        session: Any,
        user_id: str,
        runner_ctx: Dict[str, Any],
        available_weeks: int,
        constraints: Any,
        max_attempts: int = 2,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Attempt to fix validation issues by adjusting parameters and regenerating.

        Returns:
            (corrected_weeks, remaining_issues)
        """
        attempts = 0
        current_weeks = weeks_long
        current_issues = quality_issues
        adjusted_available_weeks = available_weeks

        while attempts < max_attempts and current_issues:
            # Analyze issues and determine fixes
            fixes = self._analyze_issues_for_fixes(current_issues, current_weeks)

            if not fixes:
                # No fixable issues found
                logger.debug("No fixable issues identified, stopping self-correction")
                break

            logger.info(
                f"Self-correction attempt {attempts + 1}/{max_attempts}: "
                f"Applying fixes: {fixes}"
            )

            # Apply fixes to parameters
            adjusted_available_weeks = self._apply_fixes_to_weeks(
                fixes, adjusted_available_weeks, current_weeks
            )

            # Regenerate spine with adjusted parameters
            try:
                lr_output = self.pass1.build(
                    session=session,
                    user_id=user_id,
                    plan_request=plan_request,
                    activity_weeks=runner_ctx.get("activity_weeks", 12),
                    recommended_weeks=adjusted_available_weeks,
                )
                new_weeks = lr_output.get("weeks", [])

                if not new_weeks:
                    logger.warning("Regeneration produced empty spine, stopping")
                    break

                # Re-validate
                is_valid, new_issues = validate_phase_quality(
                    new_weeks,
                    peak=self.config.target_peak_miles,
                    cutback_every=self.config.cutback_every,
                    taper_weeks=self.config.taper_weeks,
                    taper_ratios=self.config.taper_ratios,
                )

                if is_valid:
                    logger.info("✅ Self-correction successful - plan is now valid")
                    return new_weeks, []

                # Check if we made progress (fewer or different issues)
                if len(new_issues) >= len(current_issues):
                    # No improvement or worse, stop trying
                    logger.warning(
                        f"No improvement after attempt {attempts + 1} "
                        f"({len(new_issues)} issues vs {len(current_issues)} before)"
                    )
                    break

                current_weeks = new_weeks
                current_issues = new_issues
                attempts += 1

            except Exception as e:
                logger.error(f"Error during self-correction regeneration: {e}")
                break

        return current_weeks, current_issues

    def _analyze_issues_for_fixes(
        self, issues: List[str], weeks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze validation issues and determine what fixes can be applied.

        Returns:
            Dict with fix instructions, e.g.:
            {
                "taper_too_short": True,
                "reduce_build_weeks": 1,
            }
        """
        fixes = {}

        for issue in issues:
            # Fix: "Final taper week too high" - taper is incomplete
            if (
                "Final taper week too high" in issue
                or "taper week too high" in issue.lower()
            ):
                # Check if we have fewer taper weeks than expected
                lr_values = [float(w.get("long_run_miles", 0)) for w in weeks]
                if not lr_values:
                    continue

                peak_idx = lr_values.index(max(lr_values))
                taper_phase = (
                    lr_values[peak_idx + 1 :] if peak_idx + 1 < len(lr_values) else []
                )

                expected_taper_weeks = self.config.taper_weeks
                actual_taper_weeks = len(taper_phase)

                if actual_taper_weeks < expected_taper_weeks:
                    fixes["taper_too_short"] = True
                    fixes["missing_taper_weeks"] = (
                        expected_taper_weeks - actual_taper_weeks
                    )
                    logger.info(
                        f"Detected incomplete taper: {actual_taper_weeks} weeks, "
                        f"expected {expected_taper_weeks}. Need to reduce build phase."
                    )

            # Fix: "Taper too short" - need more taper weeks
            if "Taper: Too short" in issue:
                fixes["taper_too_short"] = True
                fixes["reduce_build_weeks"] = 1

        return fixes

    def _apply_fixes_to_weeks(
        self, fixes: Dict[str, Any], available_weeks: int, weeks: List[Dict[str, Any]]
    ) -> int:
        """
        Apply fixes to adjust available_weeks parameter.

        Returns:
            Adjusted available_weeks value.
        """
        adjusted = available_weeks

        # Fix: Taper too short - reduce build weeks to make room for full taper
        if fixes.get("taper_too_short"):
            missing_weeks = fixes.get("missing_taper_weeks", 1)
            reduce_by = fixes.get("reduce_build_weeks", missing_weeks)
            # Ensure we don't go below minimum plan length (typically 12 weeks)
            min_plan_length = getattr(self.config, "min_plan_length_weeks", 12)
            adjusted = max(min_plan_length, available_weeks - reduce_by)
            logger.info(
                f"Adjusting available_weeks: {available_weeks} → {adjusted} "
                f"(reducing by {reduce_by} to make room for full taper)"
            )

        return adjusted
