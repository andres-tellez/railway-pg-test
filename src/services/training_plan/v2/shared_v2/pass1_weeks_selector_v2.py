from __future__ import annotations

from typing import Any, Dict, Optional
import logging

# Removed imports: DataCollectionService, InsightsCalculationService
# This selector no longer collects data - it receives fitness metrics from Step 1


logger = logging.getLogger(__name__)


class Pass1WeeksSelector:
    """Deterministic selector for total training weeks needed.

    Leverages existing L1 (data collection) and L2 (insights) to make a
    safety-first recommendation for a "finish a marathon" goal.

    Logic (safety > date):
    - Use current base mileage from insights (weekly_mileage) as primary signal
    - Map to recommended duration:
        <15 mpw                     -> 24 weeks
        15–<20 mpw                  -> 20 weeks
        20–30 mpw                   -> 16 weeks
        >30 mpw                     -> 12 weeks

    Returns a dict with weeks and rationale for UI/telemetry.
    """

    def __init__(self):
        # No dependencies needed - receives fitness metrics as parameters
        pass

    def select_weeks(
        self,
        *,
        weekly_mileage: float,
        longest_run: float,
        plan_request: Dict[str, Any],
        available_weeks: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compute recommended training duration in weeks with rationale.
        
        Now considers both fitness AND available time when making recommendation.
        
        NOTE: This function no longer collects data. Fitness metrics must be provided
        from Step 1 (Assess Physical Level).

        Args:
            weekly_mileage: Average weekly mileage from last 4 weeks
            longest_run: Longest run in last 4 weeks
            plan_request: incoming request body
            available_weeks: Available training weeks from race date (if provided)
        Returns:
            { "weeks": int, "rationale": { ... }, "signals": { ... } }
        """
        base_mileage = float(weekly_mileage)
        longest_run_miles = float(longest_run)
        goal = (plan_request.get("primary_goal") or "finish").lower().strip()

        # Safety-first mapping (fitness-based recommendation)
        fitness_recommended_weeks = self._map_weeks(base_mileage=base_mileage)
        
        # Time-aware adjustment
        if available_weeks is not None:
            if available_weeks > fitness_recommended_weeks:
                # Extra time available: use all available time
                recommended_weeks = available_weeks
                time_adjustment = "expanded_to_fill_available_time"
                logger.info(
                    f"Pass1WeeksSelector: Fitness recommends {fitness_recommended_weeks} weeks, "
                    f"but {available_weeks} weeks available. Using {available_weeks} weeks "
                    f"to fill available time."
                )
            elif available_weeks < fitness_recommended_weeks:
                # Time-constrained: use available time (may be tight)
                recommended_weeks = available_weeks
                time_adjustment = "constrained_by_available_time"
                logger.warning(
                    f"Pass1WeeksSelector: Fitness recommends {fitness_recommended_weeks} weeks, "
                    f"but only {available_weeks} weeks available. Using {available_weeks} weeks "
                    f"(time-constrained)."
                )
            else:
                # Perfect match
                recommended_weeks = fitness_recommended_weeks
                time_adjustment = "matches_available_time"
        else:
            # No time constraint: use fitness-based recommendation
            recommended_weeks = fitness_recommended_weeks
            time_adjustment = "no_time_constraint"

        rationale = {
            "rule": "safety_first_finish_goal",
            "base_mileage_mpw": base_mileage,
            "longest_recent_run_miles": longest_run_miles,
            "primary_goal": goal,
            "mapping": "<15→24, 15–<20→20, 20–30→16, >30 or experienced→12",
            "fitness_recommended_weeks": fitness_recommended_weeks,
            "available_weeks": available_weeks,
            "time_adjustment": time_adjustment,
        }

        logger.info(
            "Pass1WeeksSelector: base=%.1f, longest=%.1f, fitness_rec=%d, available=%s -> weeks=%d (%s)",
            base_mileage,
            longest_run_miles,
            fitness_recommended_weeks,
            available_weeks,
            recommended_weeks,
            time_adjustment,
        )

        return {
            "weeks": recommended_weeks,
            "rationale": rationale,
            "signals": {
                "current_fitness": {
                    "weekly_mileage": base_mileage,
                    "longest_run": longest_run_miles,
                },
            },
        }

    @staticmethod
    def _map_weeks(*, base_mileage: float) -> int:
        if base_mileage < 15.0:
            return 24
        if base_mileage < 20.0:
            return 20
        if base_mileage <= 30.0:
            return 16
        return 12
