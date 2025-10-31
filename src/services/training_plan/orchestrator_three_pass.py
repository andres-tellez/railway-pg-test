from typing import Any, Dict, List, Optional

from src.services.training_plan.pass3_workout_distribution import (
    Pass3WorkoutDistribution,
)
from src.services.training_plan.pass4_workout_details import Pass4WorkoutDetails
from src.services.training_plan.plan_validation_service import PlanValidationService
from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)
from src.services.training_plan.pass1_longrun_first import Pass1LongRunFirst
from src.services.training_plan.weekly_total_calculator import (
    calculate_weekly_totals_from_long_runs,
)
from src.services.training_plan.pace_seed_service import get_initial_pace_seed


class ThreePassOrchestrator:
    """Three-pass plan generator: long-run-first approach.

    Uses deterministic LR-first progression, then calculates weekly totals and distributes workouts.
    """

    def __init__(self, llm_client: Optional[Any] = None):
        # llm_client is accepted for compatibility but unused in LR-first path
        self.pass3 = Pass3WorkoutDistribution()
        self.pass4 = Pass4WorkoutDetails()
        self.validator = PlanValidationService()
        self.longrun_first = Pass1LongRunFirst(
            data_collector=DataCollectionService(),
            insights_service=InsightsCalculationService(),
        )

    def generate_longrun_first(
        self,
        runner_ctx: Dict[str, Any],
        mode: str = "prefill",
        week_logs: Optional[Dict[int, List]] = None,
    ) -> Dict[str, Any]:
        """Alternate pipeline: long-run progression defines duration first.

        Steps:
          1) Pass1LongRunFirst → recommended_weeks + long_run_miles per week
          2) Weekly totals via existing Pass 1 math for the same weeks
          3) Pass 3: Distribute workouts across training days
          4) Pass 4: Add detailed segments, pace guidance, and cues
          5) Validation

        Args:
            runner_ctx: Context dict with session, user_id, plan_request, training_days
            mode: "prefill" (all weeks) or "rolling" (week 1 only)
            week_logs: Optional dict mapping week_num -> List[WeekLogRun] for adjustments

        Returns:
            Dict with validated plan and details
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
        # Collect L1 data once - will be reused by Pass1LongRunFirst internally
        # and also reused for pace seeding (avoid duplicate queries)
        raw_data = self.longrun_first.data_collector.collect_all_data(
            session=session,
            user_id=str(user_id),
            plan_request=plan_request,
            activity_weeks=12,  # Match what Pass1LongRunFirst uses
        )
        strava_activities = raw_data.get("strava_activities", [])

        # Pass raw_data to Pass1LongRunFirst (it will use it if available, otherwise collect again)
        # Note: Currently Pass1LongRunFirst collects internally - in future we can pass raw_data
        # to avoid duplicate collection. For now, we still reuse strava_activities for pace seeding.
        lr_out = self.longrun_first.build(
            session=session,
            user_id=str(user_id),
            plan_request=plan_request,
        )

        # 2) Calculate weekly totals from long runs
        runs_per_week = len(training_days) if training_days else 4

        merged = calculate_weekly_totals_from_long_runs(
            weeks=lr_out.get("weeks", []),
            runs_per_week=runs_per_week,
        )

        # 3) Pass 3: Distribute workouts across training days
        plan = self.pass3.run(merged, training_days)
        fixed = self._autofix(plan)

        # 4) Pass 4: Add detailed segments, pace guidance, and cues
        # Generate initial pace seed from Strava data (already in memory) or calibration
        first_week = fixed.get("weeks", [{}])[0] if fixed.get("weeks") else {}
        week1_total = float(first_week.get("weekly_mileage", 0) or 0)
        week1_long = float(first_week.get("long_run_miles", 0) or 0)

        # Optional: extract goal marathon pace from plan_request if available
        goal_mp_sec_per_mi = (
            None  # Could be derived from plan_request.get("target_time")
        )

        # Use Strava activities already collected in L1/L2 (no duplicate query)
        initial_seed = get_initial_pace_seed(
            strava_activities=strava_activities,
            plan_week1_total=week1_total,
            plan_week1_long=week1_long,
            goal_mp_sec_per_mi=goal_mp_sec_per_mi,
        )

        # Add details to all workouts
        plan_with_details = self.pass4.add_details_to_plan(
            plan=fixed,
            seed=initial_seed,
            mode=mode,
            week_logs=week_logs,
        )

        # 5) Validation
        result = self.validator.validate_plan(plan_with_details)
        if not result.get("valid"):
            return {
                "valid": False,
                "violations": result.get("violations", []),
                "draft": plan_with_details,
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
