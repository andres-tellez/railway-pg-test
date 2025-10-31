from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from sqlalchemy.orm import Session

from src.services.training_plan.data_collection_service import DataCollectionService
from src.services.training_plan.insights_calculation_service import (
    InsightsCalculationService,
)


logger = logging.getLogger(__name__)


class Pass1WeeksSelector:
    """Deterministic selector for total training weeks needed.

    Leverages existing L1 (data collection) and L2 (insights) to make a
    safety-first recommendation for a "finish a marathon" goal.

    Logic (safety > date):
    - Use current base mileage from insights (weekly_mileage) as primary signal
    - Experience hints from plan_request["marathon_experience"] when present
    - Map to recommended duration:
        <15 mpw or "beginner"     -> 24 weeks
        15–<20 mpw                 -> 20 weeks
        20–30 mpw                  -> 16 weeks
        >30 mpw or "experienced"   -> 12 weeks

    Returns a dict with weeks and rationale for UI/telemetry.
    """

    def __init__(
        self,
        *,
        data_collector: Optional[DataCollectionService] = None,
        insights_service: Optional[InsightsCalculationService] = None,
    ):
        self.data_collector = data_collector or DataCollectionService()
        self.insights_service = insights_service or InsightsCalculationService()

    def select_weeks(
        self,
        *,
        session: Session,
        user_id: str,
        plan_request: Dict[str, Any],
        activity_weeks: int = 12,
    ) -> Dict[str, Any]:
        """Compute recommended training duration in weeks with rationale.

        Args:
            session: DB session
            user_id: UUID string
            plan_request: incoming request body
            activity_weeks: history window for L1
        Returns:
            { "weeks": int, "rationale": { ... }, "signals": { ... } }
        """
        # L1: collect signals
        raw = self.data_collector.collect_all_data(
            session=session,
            user_id=user_id,
            plan_request=plan_request,
            activity_weeks=activity_weeks,
        )

        # L2: derive current fitness
        insights = self.insights_service.calculate_all_insights(raw)
        current = insights.get("current_fitness", {})

        base_mileage = float(current.get("weekly_mileage", 0) or 0)
        longest_run = float(current.get("longest_run", 0) or 0)
        experience = (plan_request.get("marathon_experience") or "").lower().strip()
        goal = (plan_request.get("primary_goal") or "finish").lower().strip()

        # Safety-first mapping
        recommended_weeks = self._map_weeks(
            base_mileage=base_mileage, experience=experience
        )

        rationale = {
            "rule": "safety_first_finish_goal",
            "base_mileage_mpw": base_mileage,
            "longest_recent_run_miles": longest_run,
            "experience": experience or None,
            "primary_goal": goal,
            "mapping": "<15→24, 15–<20→20, 20–30→16, >30 or experienced→12",
        }

        logger.info(
            "Pass1WeeksSelector: base=%.1f, longest=%.1f, exp=%s -> weeks=%d",
            base_mileage,
            longest_run,
            experience or "",
            recommended_weeks,
        )

        return {
            "weeks": recommended_weeks,
            "rationale": rationale,
            "signals": {
                "current_fitness": current,
                "insights": insights.get("metadata", {}),
            },
        }

    @staticmethod
    def _map_weeks(*, base_mileage: float, experience: str | None) -> int:
        exp = (experience or "").lower().strip()
        if base_mileage < 15.0 or exp == "beginner":
            return 24
        if base_mileage < 20.0:
            return 20
        if base_mileage <= 30.0:
            return 16
        return 12
