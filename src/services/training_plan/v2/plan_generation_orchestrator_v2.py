"""
Plan Generation Orchestrator V2

Wires together the race-distance-aware services to produce a deterministic draft plan.

Deprecated spine validation wrappers (still in use; remove in Phase 3 Stage D only
after migration): see ``long_run_curve_validation`` module docstring,
*DEPRECATED COMPONENTS* registry — notably ``_validate_spine_immutability`` and
call sites using ``validate_phase_quality``.

Pipeline Steps:
  Step 1: Assess Physical Level (fitness data from materialized view)
  Step 2: Calculate training weeks needed (fitness-based)
  Step 3: Calculate available time (calendar constraint)
  Step 4: Determine plan length based on scenario
  Step 4.5: Get scenario-specific adjustments
  Step 5: Build long-run progression + weekly totals
  Step 6: Distribute workouts to training days
  Step 7: Add workout details (paces, intervals, notes)
  Step 8: Final validation
"""

from typing import Any, Dict, List, Optional, Tuple
import logging
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    validate_phase_quality,
)

from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.v2.marathon.adaptive_marathon_peak import (
    RaceConfigPeakOverride,
    resolve_marathon_adaptive_target_peak_miles,
)

# DataCollectionService and InsightsCalculationService no longer needed
# All data now comes from materialized view (same as metrics page)
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
from src.services.training_plan.pace import (
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
from src.services.training_plan.v2.scenario_adjustments_service import (
    ScenarioAdjustmentsService,
)
from src.services.training_plan.v2.workout_taxonomy.workout_definitions import (
    WORKOUT_DEFINITIONS,
    get_workout_definition,
)

# Workout type constants (for backward compatibility)
EASY = "easy"
# Short labels for workout types (e.g., "Easy", "Tempo", "Intervals")
TYPE_DISPLAY = {k: k.capitalize() for k in WORKOUT_DEFINITIONS.keys()}
PACE_GUIDANCE = {k: v["pace_guidance"] for k, v in WORKOUT_DEFINITIONS.items()}
from src.services.metrics_helper_service import (
    get_weekly_fitness_from_materialized_view,
)
from src.services.training_plan.decision_trace import (
    DecisionReason,
    resolve_training_days,
    resolve_long_run_day,
)
from src.utils.timezone_helpers import resolve_timezone

logger = logging.getLogger(__name__)


class PlanGenerationOrchestratorV2:
    """
    Race-distance-aware orchestrator for the long-run-first deterministic pipeline.
    """

    def __init__(
        self,
        config: RaceDistanceConfig,
        race_type: str = "marathon",
        scenario: str = None,
    ) -> None:
        self.config = config
        self.race_type = race_type
        self.scenario = scenario
        # DataCollectionService and InsightsCalculationService removed
        # All data now comes from materialized view (same as metrics page)

        self.pass1 = Pass1LongRunFirstV2(
            config=config,
        )
        # Pass3 now uses the new WorkoutPlacementEngine with phase-aware templates
        self.pass3 = Pass3WorkoutDistribution(
            config=config,
            race_type=race_type,
            scenario=scenario,
        )
        self.pass4 = Pass4WorkoutDetails()
        self.validator = PlanValidationServiceV2(config=config, unit_system="imperial")
        self.pass1_selector = Pass1WeeksSelectorV2()
        self.constraints_service = PlanConstraintsService()
        self.race_date_validator = RaceDateValidationService(
            config=config,
            constraints_service=self.constraints_service,
        )
        self.scenario_adjustments = ScenarioAdjustmentsService()

    def generate_longrun_first(
        self,
        runner_ctx: Dict[str, Any],
        mode: str = "prefill",  # Default: detail every week
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
        unit_system = runner_ctx.get("unit_system", "imperial")

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

        training_days, training_days_reason = self._determine_training_days(
            plan_request, training_days
        )
        plan_request["training_days"] = training_days

        runs_per_week = len(training_days)

        # Note: Max HR must be entered manually in user profile
        # Strava API doesn't return max_heartrate, so manual entry is required

        # Step 1: Assess Physical Level (NEW - using materialized view)
        # Use the same process as metrics page for consistency
        # This ensures the numbers shown to the user match what's used for plan generation
        weekly_mileage, longest_run = get_weekly_fitness_from_materialized_view(
            session=session,
            user_id=str(user_id),
        )

        logger.info(
            f"📊 Step 1: Physical assessment complete - {weekly_mileage:.1f} mpw, "
            f"longest_run={longest_run:.1f}mi (from materialized view, same as metrics page)"
        )

        # Store for subsequent steps
        fitness_data = {
            "weekly_mileage": weekly_mileage,
            "longest_run": longest_run,
        }

        # Step 2: Calculate training weeks needed (fitness-based only, no dates)
        # Determine how many weeks of training the user needs to safely complete a marathon
        # Based solely on their current fitness level from Step 1
        fitness_recommended_weeks = self.pass1_selector._map_weeks(
            base_mileage=weekly_mileage
        )

        logger.info(
            f"📊 Step 2: Training weeks needed - {fitness_recommended_weeks} weeks "
            f"(based on {weekly_mileage:.1f} mpw, no date constraints)"
        )

        # Store fitness recommendation for later steps
        fitness_data["fitness_recommended_weeks"] = fitness_recommended_weeks

        # Step 3: Calculate available time
        # Calculate available weeks between earliest start date and race date
        # This is the calendar constraint (time available)
        race_date = plan_request.get("race_date")
        start_date = plan_request.get("start_date")
        user_tz = resolve_timezone(plan_request)
        if not plan_request.get("user_timezone"):
            plan_request["user_timezone"] = user_tz
        min_start_date = self.constraints_service.get_min_start_date(
            user_timezone=user_tz
        )
        available_weeks = self.constraints_service.calculate_available_weeks(
            race_date=race_date,
            min_start_date=min_start_date,
        )
        if available_weeks is not None:
            logger.info(
                f"📅 Step 3: Calculated {available_weeks} available training weeks "
                f"(race_date={race_date}, min_start={min_start_date.isoformat()})"
            )
        else:
            logger.info("📅 Step 3: No race date provided, no time constraint")

        # Step 4: Determine plan length based on scenario
        # Calculate what we'll actually BUILD
        # Scenarios:
        # 1. Time-constrained (available < fitness): Build with available_weeks
        # 2. Extra time (available > fitness): Build with available_weeks (fill all time)
        # 3. Perfect match (available == fitness): Build with available_weeks
        # 4. No time constraint (available is None): Build with fitness_recommended_weeks
        plan_length_weeks = (
            available_weeks
            if available_weeks is not None
            else fitness_recommended_weeks
        )

        if not plan_length_weeks:
            gf = {
                "failure_code": "plan_length_missing",
                "failure_reason": "Plan length in weeks could not be determined.",
                "details": {},
            }
            v = {
                "rule": "plan_length_missing",
                "severity": "error",
                "location": "plan_generation",
                **gf,
            }
            return {
                "valid": False,
                "violations": [v],
                "generation_failure": gf,
                "draft": {},
            }

        logger.info(
            f"✅ Step 4: Plan length determined - {plan_length_weeks} weeks "
            f"(fitness recommendation: {fitness_recommended_weeks} weeks, "
            f"available: {available_weeks} weeks)"
        )

        # Step 4.5: Get scenario-specific adjustments
        scenario_adjustments = self.scenario_adjustments.get_adjustments(
            fitness_recommended_weeks=fitness_recommended_weeks,
            available_weeks=available_weeks,
            base_weekly_mileage=weekly_mileage,
            plan_length_weeks=plan_length_weeks,
        )
        scenario = scenario_adjustments["scenario"]

        logger.info(
            f"📊 Step 4.5: Scenario adjustments determined - {scenario}, "
            f"starting_mileage_adjustment={scenario_adjustments['starting_mileage_adjustment']:.2f}"
        )

        gen_config = self._generation_race_config(
            weekly_mileage=weekly_mileage,
            plan_request=plan_request,
            plan_length_weeks=int(plan_length_weeks),
        )
        if self.race_type == "marathon":
            logger.info(
                "Marathon adaptive peak target: %.1f mi (mpw=%.1f, primary_goal=%s, weeks=%s)",
                gen_config.target_peak_miles,
                weekly_mileage,
                plan_request.get("primary_goal"),
                plan_length_weeks,
            )

        # Step 5: Build long run progression (scenario-aware)

        # Validate time constraints ONLY for time-constrained scenario
        # This is where the popup/warning should be shown
        race_date_validation = None
        if scenario == ScenarioAdjustmentsService.TIME_CONSTRAINED and race_date:
            # Use actual calculated values from Steps 2-4 for accuracy
            # Use start_date from plan_request or min_start_date as fallback
            plan_start_date = start_date or min_start_date
            race_date_validator = RaceDateValidationService(
                config=gen_config,
                constraints_service=self.constraints_service,
            )
            race_date_validation = race_date_validator.validate(
                race_date=race_date,
                plan_start_date=plan_start_date,
                current_weekly_mileage=weekly_mileage,
                current_long_run=longest_run,
                user_timezone=user_tz,
            )

            logger.info(
                f"⚠️ Time-constrained scenario detected: "
                f"status={race_date_validation.get('status')}, "
                f"available={race_date_validation.get('available_weeks')} weeks, "
                f"required={race_date_validation.get('required_weeks')} weeks, "
                f"can_proceed={race_date_validation.get('can_proceed', False)}"
            )

            # BLOCK plan generation if validation says we cannot proceed
            if not race_date_validation.get("can_proceed", False):
                logger.error(
                    f"❌ Plan generation blocked: insufficient time/fitness. "
                    f"Status: {race_date_validation.get('status')}, "
                    f"Available: {race_date_validation.get('available_weeks')} weeks, "
                    f"Required: {race_date_validation.get('required_weeks')} weeks"
                )
                # Return early with validation result (no plan generated)
                gf = {
                    "failure_code": "insufficient_time",
                    "failure_reason": race_date_validation.get(
                        "message",
                        "Insufficient time to safely prepare for the race on this schedule.",
                    ),
                    "details": {
                        "available_weeks": race_date_validation.get("available_weeks"),
                        "required_weeks": race_date_validation.get("required_weeks"),
                        "recommendation": race_date_validation.get("recommendation"),
                    },
                }
                return {
                    "valid": False,
                    "violations": [
                        {
                            "rule": "insufficient_time",
                            "severity": "error",
                            "location": "plan_generation",
                            "failure_code": gf["failure_code"],
                            "failure_reason": gf["failure_reason"],
                            "details": gf["details"],
                            "suggestion": race_date_validation.get(
                                "recommendation",
                                "Adjust race date or build base fitness first",
                            ),
                        }
                    ],
                    "generation_failure": gf,
                    "validated_plan": None,
                    "race_date_validation": race_date_validation,
                }

        # Build spine (scenario-specific configuration will be added later)
        pass1_gen = Pass1LongRunFirstV2(config=gen_config)
        lr_output = pass1_gen.build(
            session=session,
            user_id=str(user_id),
            weekly_mileage=weekly_mileage,
            longest_run=longest_run,
            plan_request=plan_request,
            recommended_weeks=plan_length_weeks,
            unit_system=unit_system,
        )
        weeks_long = lr_output.get("weeks", [])

        if len(weeks_long) != plan_length_weeks:
            logger.warning(
                "Spine length mismatch: requested %s weeks, generated %s weeks",
                plan_length_weeks,
                len(weeks_long),
            )

        spine_err = self._validate_spine_immutability(
            weeks_long, gen_config.target_peak_miles
        )
        if spine_err:
            gf = {
                "failure_code": spine_err.get(
                    "failure_code", "spine_validation_failed"
                ),
                "failure_reason": spine_err.get(
                    "failure_reason", "Long-run spine validation failed."
                ),
                "details": spine_err.get("details", {}),
            }
            return {
                "valid": False,
                "violations": [spine_err],
                "generation_failure": gf,
                "draft": {},
            }

        # GUARDRAIL: Validate spine quality - check cutback spacing, progression, etc.
        # DEPRECATED: validate_phase_quality facade (TODO Stage D → validate_long_run_curve).
        is_valid, quality_issues = validate_phase_quality(
            weeks_long,
            peak=gen_config.target_peak_miles,
            cutback_every=gen_config.cutback_every,
            taper_weeks=gen_config.taper_weeks,
            taper_ratios=gen_config.taper_ratios,
            race_config=gen_config,
        )

        # Self-correction: Try to fix validation issues automatically
        if not is_valid:
            logger.warning(
                f"Spine quality validation failed: {'; '.join(quality_issues)}. "
                f"Attempting self-correction..."
            )
            corrected_weeks, remaining_issues = self._self_correct_spine(
                session=session,
                user_id=str(user_id),
                weekly_mileage=weekly_mileage,
                longest_run=longest_run,
                weeks_long=weeks_long,
                quality_issues=quality_issues,
                plan_request=plan_request,
                recommended_weeks=plan_length_weeks,  # Use actual plan length for self-correction
                scenario_adjustments=scenario_adjustments,
                max_attempts=2,
                unit_system=unit_system,
                race_config=gen_config,
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

        # Weekly totals from long runs (with scenario adjustments)
        weeks_with_totals = calculate_weekly_totals_from_long_runs(
            weeks=weeks_long,
            runs_per_week=runs_per_week,
            config=gen_config,
            scenario_adjustments=scenario_adjustments,
            unit_system=unit_system,
        )

        # Step 6: Distribute workouts to training days
        # Determine long run day (user preference or auto-select)
        long_run_day, long_run_day_reason = self._determine_long_run_day(
            plan_request, training_days
        )

        pass3_gen = Pass3WorkoutDistribution(
            config=gen_config,
            race_type=self.race_type,
            scenario=self.scenario,
        )
        pass3_plan = pass3_gen.run(
            weeks_with_totals,
            training_days,
            total_weeks=plan_length_weeks,
            long_run_day=long_run_day,
            unit_system=unit_system,
        )

        weeks_out = pass3_plan.get("weeks", [])

        # GUARDRAIL: No post-processing of spine - progression is calculated once in spine generator
        # If plan needs adjustment, regenerate with different parameters, don't modify

        weeks_out = self._append_race_week(weeks_out, unit_system=unit_system)
        logger.info("After race week append: %s total weeks", len(weeks_out))

        weeks_out, aligned_start_date = self.constraints_service.align_weeks_with_dates(
            weeks=weeks_out,
            race_date=race_date,
            min_start_date=min_start_date,
            fallback_start=start_date,
        )
        if aligned_start_date:
            logger.info(
                "Aligned plan dates: start=%s end=%s length=%s",
                aligned_start_date,
                weeks_out[-1].get("week_start_date") if weeks_out else None,
                len(weeks_out),
            )

        if aligned_start_date:
            plan_request["start_date"] = aligned_start_date.isoformat()

        # Post-race cleanse: Remove any workout scheduled for the day after race
        weeks_out = self._remove_post_race_workouts(weeks_out, race_date)

        # Pace seed (performance-based calculation from recent run data)
        pace_seed = self._derive_pace_seed(
            lr_output, plan_request, weeks_out, user_id=str(user_id), session=session
        )

        # Step 7: Add workout details (paces, intervals, notes)
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

        # Step 8: Final validation
        validator_gen = PlanValidationServiceV2(
            config=gen_config, unit_system=unit_system
        )
        validation = validator_gen.validate_plan(
            plan_with_details, unit_system=unit_system
        )
        validation["draft"] = plan_with_details
        validation["pass1_rationale"] = lr_output.get("rationale")
        validation["decision_trace"] = [
            training_days_reason.to_dict(),
            long_run_day_reason.to_dict(),
        ]
        # Include race date validation results if available
        if race_date_validation:
            validation["race_date_validation"] = race_date_validation

        if self.race_type == "marathon":
            validation["peak_target_long_run_miles"] = gen_config.target_peak_miles

        # Include spine quality validation results
        # This checks cutback spacing, progression safety, peak achievement, etc.
        validation["spine_quality"] = {
            "is_valid": is_valid,
            "issues": quality_issues,
        }

        return validation

    # NOTE: Date parsing and start date calculation moved to PlanConstraintsService
    # for better separation of concerns and consistency across components

    def _determine_scenario(
        self,
        fitness_recommended_weeks: int,
        available_weeks: Optional[int],
    ) -> str:
        """
        Determine which scenario we're in based on Step 4 comparison.

        Returns:
            "time_constrained" | "extra_time" | "perfect_match" | "no_constraint"
        """
        if available_weeks is None:
            return "no_constraint"
        elif available_weeks < fitness_recommended_weeks:
            return "time_constrained"
        elif available_weeks > fitness_recommended_weeks:
            return "extra_time"
        else:
            return "perfect_match"

    def _determine_training_days(
        self,
        plan_request: Dict[str, Any],
        requested_training_days: Optional[List[str]],
    ) -> Tuple[List[str], DecisionReason]:
        """Resolve training_days via shared decision trace helper."""
        return resolve_training_days(
            plan_request=plan_request,
            hints=plan_request.get("coach_memory_hints") or [],
            memories=plan_request.get("coach_memory_memories") or [],
            requested_training_days=requested_training_days,
        )

    def _determine_long_run_day(
        self,
        plan_request: Dict[str, Any],
        training_days: List[str],
    ) -> Tuple[str, DecisionReason]:
        """Resolve long_run_day via shared decision trace helper."""
        user_preference = plan_request.get("long_run_day")
        if user_preference and user_preference not in training_days:
            logger.warning(
                f"User-specified long_run_day '{user_preference}' not in training_days "
                f"{training_days}, falling back to auto-selection"
            )
        return resolve_long_run_day(
            plan_request=plan_request,
            hints=plan_request.get("coach_memory_hints") or [],
            memories=plan_request.get("coach_memory_memories") or [],
            training_days=training_days,
        )

    def _generation_race_config(
        self,
        *,
        weekly_mileage: float,
        plan_request: Dict[str, Any],
        plan_length_weeks: int,
    ) -> RaceDistanceConfig:
        """Race config for this generation (marathon uses adaptive peak long run)."""
        if self.race_type != "marathon":
            return self.config
        peak = resolve_marathon_adaptive_target_peak_miles(
            weekly_mileage=weekly_mileage,
            primary_goal=plan_request.get("primary_goal"),
            plan_length_weeks=plan_length_weeks,
        )
        if abs(peak - self.config.target_peak_miles) < 0.01:
            return self.config
        return RaceConfigPeakOverride(self.config, peak)

    def _validate_spine_immutability(
        self, weeks: List[Dict[str, Any]], peak_target: float
    ) -> Optional[Dict[str, Any]]:
        """
        GUARDRAIL: Validate that spine hasn't been modified after generation.

        DEPRECATED — replaced by ``validate_long_run_curve`` (call directly with
        structure + peak-max flags). TODO Phase 3 Stage D: delete this method after
        inlining. See ``long_run_curve_validation`` DEPRECATED COMPONENTS registry.

        Returns a structured violation dict if invalid; otherwise None.
        """
        from src.services.training_plan.v2.shared_v2.long_run_curve_validation import (
            orchestrator_issue_to_violation_dict,
            validate_long_run_curve,
        )

        curve = [float(w.get("long_run_miles", 0) or 0) for w in weeks]
        issues = validate_long_run_curve(
            curve,
            self.config,
            spine_rows=weeks,
            expected_start_miles=None,
            peak_target_miles=float(peak_target),
            taper_ratios_override=list(self.config.taper_ratios),
            cutback_every_override=int(self.config.cutback_every),
            taper_weeks_override=int(self.config.taper_weeks),
            include_structure_checks=True,
            include_peak_max_check=True,
            include_pass1_progression=False,
            include_phase_quality=False,
        )
        for issue in issues:
            if issue["severity"] == "error":
                return orchestrator_issue_to_violation_dict(issue)

        max_lr = max(float(w.get("long_run_miles", 0) or 0) for w in weeks)
        logger.debug(
            "Spine validation passed: %s weeks, peak %.1f miles (target %.1f)",
            len(weeks),
            max_lr,
            peak_target,
        )
        return None

    def _append_race_week(
        self, weeks: List[Dict[str, Any]], unit_system: str = "imperial"
    ) -> List[Dict[str, Any]]:
        if not weeks:
            return weeks

        template = self.config.race_week_template()
        race_week = {
            "week_number": len(weeks) + 1,
            "phase": template.get("phase", "Race Week"),
            "weekly_mileage": template.get("weekly_mileage", 0),
            "long_run_miles": template.get("long_run_miles", 0),
            "is_peak_week": False,
            "is_cutback": False,  # Race week is NOT a cutback
            "workouts": [
                self._build_race_week_workout(workout_spec, unit_system=unit_system)
                for workout_spec in template.get("workouts", [])
            ],
        }
        weeks.append(race_week)
        return weeks

    def _remove_post_race_workouts(
        self, weeks: List[Dict[str, Any]], race_date: Any
    ) -> List[Dict[str, Any]]:
        """
        Remove any workout scheduled for the day after race day.

        The runner should NEVER have a run the day after the race,
        regardless of whether the race is on Saturday or Sunday.

        Args:
            weeks: List of week dicts with workouts
            race_date: Race date (any format)

        Returns:
            Updated weeks with post-race day workouts removed
        """
        from datetime import timedelta

        if not weeks or not race_date:
            return weeks

        # Parse race date
        race_d = self.constraints_service._parse_date(race_date)
        if not race_d:
            return weeks

        # Day after race = REST
        day_after_race = race_d + timedelta(days=1)
        day_after_iso = day_after_race.isoformat()

        # Find and remove workouts on the day after race
        removed_count = 0
        for week in weeks:
            workouts = week.get("workouts", [])
            original_count = len(workouts)

            # Filter out workouts on day after race
            week["workouts"] = [w for w in workouts if w.get("date") != day_after_iso]

            removed_count += original_count - len(week["workouts"])

        if removed_count > 0:
            logger.info(
                f"Post-race cleanse: Removed {removed_count} workout(s) "
                f"scheduled for {day_after_iso} (day after race)"
            )

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

    def _build_race_week_workout(
        self,
        spec: Dict[str, Any],
        unit_system: str = "imperial",  # Deprecated: kept for backward compatibility
    ) -> Dict[str, Any]:
        from src.services.training_plan.v2.shared_v2.rounding_utils import (
            round_workout_distance,
        )

        kind = str(spec.get("kind", "easy")).lower()
        day = spec.get("day") or "Mon"
        miles = float(spec.get("miles", 0) or 0)
        note = spec.get("note")
        if kind == "race":
            # Race distance should NOT be rounded (it's a specific distance like 26.2 miles)
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
        # Round shakeout/easy runs in race week (but not the race distance itself)
        # Frontend will convert to km for display using toDisplayDistance()
        rounded_miles = round_workout_distance(miles)
        return self._easy_workout(
            day, rounded_miles, note=note, shakeout=bool(spec.get("shakeout"))
        )

    def _derive_pace_seed(
        self,
        lr_output: Dict[str, Any],
        plan_request: Dict[str, Any],
        weeks_out: List[Dict[str, Any]],
        user_id: str,
        session: Session,
    ) -> PaceSeed:
        """Create an initial pace seed using performance-based calculation from recent run data."""
        week1 = weeks_out[0] if weeks_out else {}
        week1_total = float(week1.get("weekly_mileage", 0) or 0)
        week1_long = float(week1.get("long_run_miles", 0) or 0)

        # Calculate pace seed using performance-based calculation or calibration
        seed = get_initial_pace_seed(
            session=session,
            user_id=user_id,
            week1_long=week1_long,
            lookback_weeks=6,
        )
        return seed

    def _self_correct_spine(
        self,
        session: Session,
        user_id: str,
        weekly_mileage: float,
        longest_run: float,
        weeks_long: List[Dict[str, Any]],
        quality_issues: List[str],
        plan_request: Dict[str, Any],
        recommended_weeks: int,
        scenario_adjustments: Optional[Dict[str, Any]] = None,
        max_attempts: int = 2,
        unit_system: str = "imperial",
        race_config: Optional[RaceDistanceConfig] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Attempt to fix validation issues by adjusting parameters and regenerating.

        Uses the actual plan length to maintain correct plan structure.

        Returns:
            (corrected_weeks, remaining_issues)
        """
        attempts = 0
        current_weeks = weeks_long
        current_issues = quality_issues
        adjusted_recommended_weeks = recommended_weeks
        cfg = race_config or self.config
        pass1_local = Pass1LongRunFirstV2(config=cfg)

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
            adjusted_recommended_weeks = self._apply_fixes_to_weeks(
                fixes, adjusted_recommended_weeks, current_weeks
            )

            # Regenerate spine with adjusted parameters
            try:
                lr_output = pass1_local.build(
                    session=session,
                    user_id=user_id,
                    weekly_mileage=weekly_mileage,
                    longest_run=longest_run,
                    plan_request=plan_request,
                    recommended_weeks=adjusted_recommended_weeks,
                    unit_system=unit_system,
                )
                new_weeks = lr_output.get("weeks", [])

                if not new_weeks:
                    logger.warning("Regeneration produced empty spine, stopping")
                    break

                # Re-validate (DEPRECATED: validate_phase_quality — TODO Stage D).
                is_valid, new_issues = validate_phase_quality(
                    new_weeks,
                    peak=cfg.target_peak_miles,
                    cutback_every=cfg.cutback_every,
                    taper_weeks=cfg.taper_weeks,
                    taper_ratios=cfg.taper_ratios,
                    race_config=cfg,
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
            # Fix: "Taper too short" - need more taper weeks
            if "Taper: Too short" in issue:
                fixes["taper_too_short"] = True
                fixes["reduce_build_weeks"] = 1

        return fixes

    def _apply_fixes_to_weeks(
        self, fixes: Dict[str, Any], recommended_weeks: int, weeks: List[Dict[str, Any]]
    ) -> int:
        """
        Apply fixes to adjust recommended_weeks parameter.

        ARCHITECTURAL GUARDRAIL: Works with recommended_weeks (fitness-based), not available_weeks (date-constrained)

        Returns:
            Adjusted recommended_weeks value.
        """
        adjusted = recommended_weeks

        # Fix: Taper too short - reduce build weeks to make room for full taper
        if fixes.get("taper_too_short"):
            missing_weeks = fixes.get("missing_taper_weeks", 1)
            reduce_by = fixes.get("reduce_build_weeks", missing_weeks)
            # Ensure we don't go below minimum plan length (typically 12 weeks)
            min_plan_length = getattr(self.config, "min_plan_length_weeks", 12)
            adjusted = max(min_plan_length, recommended_weeks - reduce_by)
            logger.info(
                f"Adjusting recommended_weeks: {recommended_weeks} → {adjusted} "
                f"(reducing by {reduce_by} to make room for full taper)"
            )

        return adjusted
