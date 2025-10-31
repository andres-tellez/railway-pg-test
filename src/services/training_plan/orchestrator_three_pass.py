from typing import Any, Dict, List

from src.services.training_plan.gpt_coach_pass1_weekly import GptCoachPass1Weekly
from src.services.training_plan.gpt_coach_pass2_longrun import GptCoachPass2LongRun
from src.services.training_plan.pass3_workout_distribution import (
    Pass3WorkoutDistribution,
)
from src.services.training_plan.plan_validation_service import PlanValidationService
from src.services.training_plan.pass1_weeks_selector import Pass1WeeksSelector
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.pass1_longrun_first import Pass1LongRunFirst
from src.services.training_plan.weekly_total_calculator import (
    calculate_weekly_totals_from_long_runs,
)


class ThreePassOrchestrator:
    """Three-pass plan generator: weekly totals → long runs → workouts.

    Keeps global math correct before filling details.
    """

    def __init__(self, llm_client: Any):
        self.pass1 = GptCoachPass1Weekly(llm_client)
        self.pass2 = GptCoachPass2LongRun(llm_client)
        self.pass3 = Pass3WorkoutDistribution()
        self.validator = PlanValidationService()
        self.weeks_selector = Pass1WeeksSelector(
            data_collector=DataCollectionService(),
            insights_service=InsightsCalculationService(),
        )
        self.longrun_first = Pass1LongRunFirst(
            data_collector=DataCollectionService(),
            insights_service=InsightsCalculationService(),
        )

    def generate(self, runner_ctx: Dict[str, Any]) -> Dict[str, Any]:
        # runner_ctx is expected to include session, user_id, and plan_request to allow Pass1 assessment
        session = runner_ctx.get("session")
        user_id = runner_ctx.get("user_id")
        plan_request = runner_ctx.get("plan_request", {})
        training_days = runner_ctx.get("training_days", ["Mon", "Wed", "Thu", "Sat"])

        # New deterministic Pass 1: derive weeks via L1/L2 assessment
        if session is not None and user_id is not None:
            p1 = self.weeks_selector.select_weeks(
                session=session,
                user_id=str(user_id),
                plan_request=plan_request,
            )
            weeks = int(p1["weeks"]) if isinstance(p1, dict) else int(p1)
        else:
            weeks = int(runner_ctx.get("weeks", 16))

        # Pass 1
        skel_a = self.pass1.run(
            {
                "weeks": weeks,
                "current_weekly_mileage": runner_ctx.get("current_weekly_mileage", 0),
                "longest_recent_run": runner_ctx.get("longest_recent_run", 0),
            }
        )

        # Pass 2
        skel_b = self.pass2.run(skel_a)

        # Pass 3
        plan = self.pass3.run(skel_b, training_days)

        # Minimal auto-fix: ensure weekly_mileage equals the sum of workouts
        fixed = self._autofix(plan)

        result = self.validator.validate_plan(fixed)
        if not result["valid"]:
            return {"valid": False, "violations": result["violations"], "draft": fixed}
        return {"valid": True, "validated_plan": result["validated_plan"]}

    def generate_longrun_first(self, runner_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Alternate pipeline: long-run progression defines duration first.

        Steps:
          1) Pass1LongRunFirst → recommended_weeks + long_run_miles per week
          2) Weekly totals via existing Pass 1 math for the same weeks
          3) Merge long_run_miles with a share guard (≥ 25% and ≤ 35% where possible)
          4) Pass 3 workouts, then validation
        """
        session = runner_ctx.get("session")
        user_id = runner_ctx.get("user_id")
        plan_request = runner_ctx.get("plan_request", {})
        training_days = runner_ctx.get("training_days", ["Mon", "Wed", "Thu", "Sat"])
        experience = (runner_ctx.get("experience") or "").lower().strip()

        if session is None or user_id is None:
            return {
                "valid": False,
                "violations": [
                    {
                        "rule": "context_missing",
                        "severity": "error",
                        "details": "session/user_id missing",
                    }
                ],
            }

        # 1) Long-run progression and duration
        lr_out = self.longrun_first.build(
            session=session,
            user_id=str(user_id),
            plan_request=plan_request,
        )
        # 2) Calculate weekly totals from long runs (NEW: finisher-friendly calculator)
        # Get runs_per_week from training_days
        runs_per_week = len(training_days) if training_days else 4

        # Use new weekly total calculator (preserves long runs, calculates totals)
        merged = calculate_weekly_totals_from_long_runs(
            weeks=lr_out.get("weeks", []),
            runs_per_week=runs_per_week,
        )

        # 4) Pass 3 workouts and validation
        plan = self.pass3.run(merged, training_days)
        fixed = self._autofix(plan)
        result = self.validator.validate_plan(fixed)
        if not result.get("valid"):
            return {
                "valid": False,
                "violations": result.get("violations", []),
                "draft": fixed,
            }
        return {"valid": True, "validated_plan": result["validated_plan"]}

    def _autofix(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        for w in plan.get("weeks", []):
            total = 0.0
            for x in w.get("workouts", []):
                try:
                    total += float(x.get("distance_miles", x.get("miles", 0)) or 0)
                except Exception:
                    continue
            w["weekly_mileage"] = round(total, 1)
        return plan
