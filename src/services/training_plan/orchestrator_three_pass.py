from typing import Any, Dict, List, Optional

from src.services.training_plan.pass3_workout_distribution import (
    Pass3WorkoutDistribution,
)
from src.services.training_plan.plan_validation_service import PlanValidationService
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.pass1_longrun_first import Pass1LongRunFirst
from src.services.training_plan.weekly_total_calculator import (
    calculate_weekly_totals_from_long_runs,
)


class ThreePassOrchestrator:
    """Three-pass plan generator: long-run-first approach.

    Uses deterministic LR-first progression, then calculates weekly totals and distributes workouts.
    """

    def __init__(self, llm_client: Optional[Any] = None):
        # llm_client is accepted for compatibility but unused in LR-first path
        self.pass3 = Pass3WorkoutDistribution()
        self.validator = PlanValidationService()
        self.longrun_first = Pass1LongRunFirst(
            data_collector=DataCollectionService(),
            insights_service=InsightsCalculationService(),
        )

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
