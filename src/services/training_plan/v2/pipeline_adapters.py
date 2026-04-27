"""
Pipeline stage adapters for V2 plan generation.

Adapter contract
----------------
Each adapter:

- Takes a :class:`~src.services.training_plan.v2.plan_context.PlanContext` in and returns it.
- Does not redesign plan data structures; it fills context fields the same way the inline
  orchestrator blocks did.
- Preserves deterministic behavior by mirroring existing orchestrator logic (including calls
  into shared services).
- Is not the place for new product logic or alternate algorithms; add behavior in shared
  services or change the orchestrator contract explicitly.

Each adapter mirrors the corresponding block in
:class:`~src.services.training_plan.v2.plan_generation_orchestrator_v2.PlanGenerationOrchestratorV2`.

Prerequisites on ``context`` (set before running the chain; use ``setattr`` on the
:class:`~src.services.training_plan.v2.plan_context.PlanContext` instance when a value is not
yet a dataclass field):

- ``runner_ctx``: same dict the orchestrator receives (session, user_id, plan_request, …).
- ``fitness``, ``plan_length_weeks``, ``scenario_adjustments``: as on ``PlanContext``.
- ``available_weeks``: calendar available weeks (or None), matching orchestrator locals.
- ``_race_date_validation``: optional race-date validation payload (or None).
- ``adapter_mode``, ``adapter_week_logs``: Pass4 ``mode`` and ``week_logs`` (optional;
  default ``prefill`` and ``{}``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, TYPE_CHECKING

from src.services.training_plan.v2.marathon.pass1_longrun_first_v2 import (
    Pass1LongRunFirstV2,
)
from src.services.training_plan.v2.marathon.weekly_total_calculator_v2 import (
    calculate_weekly_totals_from_long_runs,
)
from src.services.training_plan.v2.pass3_workout_distribution_v2 import (
    Pass3WorkoutDistribution,
)
from src.services.training_plan.v2.plan_context import PlanContext
from src.services.training_plan.v2.plan_validation_service_v2 import (
    PlanValidationServiceV2,
)
from src.services.training_plan.v2.shared_v2.long_run_curve_validation import (
    orchestrator_issue_to_violation_dict,
    validate_long_run_curve,
)
from src.utils.timezone_helpers import resolve_timezone

if TYPE_CHECKING:
    from src.services.training_plan.v2.plan_generation_orchestrator_v2 import (
        PlanGenerationOrchestratorV2,
    )

logger = logging.getLogger(__name__)


class Pass1Adapter:
    """Spine: Pass1 build, curve validation, self-correction (orchestrator Step 5 start)."""

    def __init__(self, orchestrator: PlanGenerationOrchestratorV2) -> None:
        self._orch = orchestrator

    def execute(self, context: PlanContext) -> PlanContext:
        runner_ctx = context.runner_ctx
        session = runner_ctx.get("session")
        user_id = runner_ctx.get("user_id")
        plan_request = runner_ctx.get("plan_request", {})
        unit_system = runner_ctx.get("unit_system", "imperial")

        weekly_mileage = context.fitness["weekly_mileage"]
        longest_run = context.fitness["longest_run"]
        plan_length_weeks = context.plan_length_weeks
        scenario_adjustments = context.scenario_adjustments

        gen_config = getattr(context, "gen_config", None)
        if gen_config is None:
            gen_config = self._orch._generation_race_config(
                weekly_mileage=weekly_mileage,
                plan_request=plan_request,
                plan_length_weeks=int(plan_length_weeks),
            )
            setattr(context, "gen_config", gen_config)

            if self._orch.race_type == "marathon":
                logger.info(
                    "Marathon adaptive peak target: %.1f mi (mpw=%.1f, primary_goal=%s, weeks=%s)",
                    gen_config.target_peak_miles,
                    weekly_mileage,
                    plan_request.get("primary_goal"),
                    plan_length_weeks,
                )

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
        context.pass1_output = lr_output
        weeks_long = lr_output.get("weeks", [])

        if len(weeks_long) != plan_length_weeks:
            logger.warning(
                "Spine length mismatch: requested %s weeks, generated %s weeks",
                plan_length_weeks,
                len(weeks_long),
            )

        curve_lr = [float(w.get("long_run_miles", 0) or 0) for w in weeks_long]
        imm_issues = validate_long_run_curve(
            curve_lr,
            gen_config,
            spine_rows=weeks_long,
            expected_start_miles=None,
            peak_target_miles=float(gen_config.target_peak_miles),
            taper_ratios_override=list(gen_config.taper_ratios),
            cutback_every_override=int(gen_config.cutback_every),
            taper_weeks_override=int(gen_config.taper_weeks),
            include_structure_checks=True,
            include_peak_max_check=True,
            include_pass1_progression=False,
            include_phase_quality=False,
        )
        spine_err = None
        for issue in imm_issues:
            if issue["severity"] == "error":
                spine_err = orchestrator_issue_to_violation_dict(issue)
                break
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
            setattr(
                context,
                "_abort_return",
                {
                    "valid": False,
                    "violations": [spine_err],
                    "generation_failure": gf,
                    "draft": {},
                },
            )
            return context

        phase_issues = validate_long_run_curve(
            curve_lr,
            gen_config,
            spine_rows=weeks_long,
            expected_start_miles=None,
            peak_target_miles=float(gen_config.target_peak_miles),
            taper_ratios_override=list(gen_config.taper_ratios),
            cutback_every_override=int(gen_config.cutback_every),
            taper_weeks_override=int(gen_config.taper_weeks),
            include_structure_checks=False,
            include_peak_max_check=False,
            include_pass1_progression=False,
            include_phase_quality=True,
        )
        quality_issues = [i["message"] for i in phase_issues]
        is_valid = len(quality_issues) == 0

        # Self-correction: Try to fix validation issues automatically
        if not is_valid:
            logger.warning(
                f"Spine quality validation failed: {'; '.join(quality_issues)}. "
                f"Attempting self-correction..."
            )
            corrected_weeks, remaining_issues = self._orch._self_correct_spine(
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

        context.spine_weeks = weeks_long
        setattr(context, "_spine_quality_is_valid", is_valid)
        setattr(context, "_spine_quality_issues", quality_issues)
        return context


class WeeklyTotalsAdapter:
    """Weekly totals from long runs (orchestrator block after spine)."""

    def __init__(self, orchestrator: PlanGenerationOrchestratorV2) -> None:
        self._orch = orchestrator

    def execute(self, context: PlanContext) -> PlanContext:
        runner_ctx = context.runner_ctx
        plan_request = runner_ctx.get("plan_request", {})
        training_days = plan_request["training_days"]
        runs_per_week = len(training_days)
        unit_system = runner_ctx.get("unit_system", "imperial")

        weeks_long = context.spine_weeks
        gen_config = context.gen_config
        scenario_adjustments = context.scenario_adjustments

        weeks_with_totals = calculate_weekly_totals_from_long_runs(
            weeks=weeks_long,
            runs_per_week=runs_per_week,
            config=gen_config,
            scenario_adjustments=scenario_adjustments,
            unit_system=unit_system,
        )
        context.weekly_totals = weeks_with_totals
        return context


class Pass3Adapter:
    """Distribution through pre–Pass4 plan dict (Pass3 + race week + dates + cleanse + pace seed)."""

    def __init__(self, orchestrator: PlanGenerationOrchestratorV2) -> None:
        self._orch = orchestrator

    def execute(self, context: PlanContext) -> PlanContext:
        runner_ctx = context.runner_ctx
        session = runner_ctx.get("session")
        user_id = runner_ctx.get("user_id")
        plan_request = runner_ctx.get("plan_request", {})
        unit_system = runner_ctx.get("unit_system", "imperial")

        training_days = plan_request["training_days"]
        plan_length_weeks = context.plan_length_weeks
        gen_config = context.gen_config
        weeks_with_totals = context.weekly_totals
        lr_output = context.pass1_output

        race_date = plan_request.get("race_date")
        start_date = plan_request.get("start_date")
        user_tz = resolve_timezone(plan_request)
        if not plan_request.get("user_timezone"):
            plan_request["user_timezone"] = user_tz
        min_start_date = self._orch.constraints_service.get_min_start_date(
            user_timezone=user_tz
        )

        long_run_day, long_run_day_reason = self._orch._determine_long_run_day(
            plan_request, training_days
        )
        setattr(context, "_long_run_day_reason", long_run_day_reason)

        pass3_gen = Pass3WorkoutDistribution(
            config=gen_config,
            race_type=self._orch.race_type,
            scenario=self._orch.scenario,
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

        weeks_out = self._orch._append_race_week(weeks_out, unit_system=unit_system)
        logger.info("After race week append: %s total weeks", len(weeks_out))

        weeks_out, aligned_start_date = (
            self._orch.constraints_service.align_weeks_with_dates(
                weeks=weeks_out,
                race_date=race_date,
                min_start_date=min_start_date,
                fallback_start=start_date,
            )
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
        weeks_out = self._orch._remove_post_race_workouts(weeks_out, race_date)

        # Pace seed (performance-based calculation from recent run data)
        pace_seed = self._orch._derive_pace_seed(
            lr_output, plan_request, weeks_out, user_id=str(user_id), session=session
        )
        setattr(context, "_pace_seed", pace_seed)

        # Step 7: Add workout details (paces, intervals, notes)
        plan_with_details = {
            "weeks": weeks_out,
            "start_date": plan_request.get("start_date"),
            "race_date": race_date,
        }
        context.workout_distribution = plan_with_details
        return context


class Pass4Adapter:
    """Workout details (orchestrator Pass4 block)."""

    def __init__(self, orchestrator: PlanGenerationOrchestratorV2) -> None:
        self._orch = orchestrator

    def execute(self, context: PlanContext) -> PlanContext:
        plan_with_details = context.workout_distribution
        pace_seed = getattr(context, "_pace_seed")
        mode = getattr(context, "adapter_mode", "prefill")
        week_logs: Dict[int, List] = getattr(context, "adapter_week_logs", None) or {}

        plan_with_details = self._orch.pass4.add_details_to_plan(
            plan=plan_with_details,
            seed=pace_seed,
            mode=mode,
            week_logs=week_logs,
        )
        context.detailed_plan = plan_with_details
        return context


class ValidationAdapter:
    """Final validation payload (orchestrator Step 8)."""

    def __init__(self, orchestrator: PlanGenerationOrchestratorV2) -> None:
        self._orch = orchestrator

    def execute(self, context: PlanContext) -> PlanContext:
        runner_ctx = context.runner_ctx
        plan_request = runner_ctx.get("plan_request", {})
        unit_system = runner_ctx.get("unit_system", "imperial")
        gen_config = context.gen_config
        plan_with_details = context.detailed_plan
        lr_output = context.pass1_output

        training_days_reason = getattr(context, "_training_days_reason", None)
        if training_days_reason is None:
            _, training_days_reason = self._orch._determine_training_days(
                plan_request, runner_ctx.get("training_days")
            )
        long_run_day_reason = getattr(context, "_long_run_day_reason")

        race_date_validation = getattr(context, "_race_date_validation", None)
        is_valid = getattr(context, "_spine_quality_is_valid")
        quality_issues = getattr(context, "_spine_quality_issues")
        scenario = context.scenario_adjustments["scenario"]
        available_weeks = getattr(context, "available_weeks", None)
        fitness_recommended_weeks = context.fitness["fitness_recommended_weeks"]

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

        if self._orch.race_type == "marathon":
            validation["peak_target_long_run_miles"] = gen_config.target_peak_miles

        # Include spine quality validation results
        # This checks cutback spacing, progression safety, peak achievement, etc.
        validation["spine_quality"] = {
            "is_valid": is_valid,
            "issues": quality_issues,
        }

        context.validation = validation
        context.metadata = {
            "scenario": scenario,
            "available_weeks": available_weeks,
            "fitness_recommended_weeks": fitness_recommended_weeks,
            "race_date_validation": race_date_validation,
        }
        context.decision_trace = validation["decision_trace"]
        return context
