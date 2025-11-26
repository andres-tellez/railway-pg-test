"""
Scenario Adjustments Service

Provides scenario-specific adjustments for plan generation based on available time
and fitness recommendations. Ensures plans are appropriately conservative or
aggressive based on the training timeline.

Scenarios:
1. Time-constrained: available_weeks < fitness_recommended_weeks
2. Extra time: available_weeks > fitness_recommended_weeks
3. Perfect match: available_weeks == fitness_recommended_weeks
4. No time constraint: available_weeks is None
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ScenarioAdjustmentsService:
    """Provides scenario-specific adjustments for plan generation."""

    # Scenario type constants
    TIME_CONSTRAINED = "time_constrained"
    EXTRA_TIME = "extra_time"
    PERFECT_MATCH = "perfect_match"
    NO_TIME_CONSTRAINT = "no_time_constraint"

    def __init__(self) -> None:
        """Initialize the scenario adjustments service."""
        pass

    def determine_scenario(
        self,
        fitness_recommended_weeks: int,
        available_weeks: Optional[int],
    ) -> str:
        """
        Determine the scenario based on fitness recommendation and available time.

        Args:
            fitness_recommended_weeks: Weeks needed based on fitness level
            available_weeks: Weeks available between start and race date (None if no race date)

        Returns:
            Scenario type string (TIME_CONSTRAINED, EXTRA_TIME, PERFECT_MATCH, NO_TIME_CONSTRAINT)
        """
        if available_weeks is None:
            return self.NO_TIME_CONSTRAINT

        if available_weeks < fitness_recommended_weeks:
            return self.TIME_CONSTRAINED
        elif available_weeks > fitness_recommended_weeks:
            return self.EXTRA_TIME
        else:
            return self.PERFECT_MATCH

    def get_starting_mileage_adjustment(
        self,
        scenario: str,
        base_weekly_mileage: float,
        plan_length_weeks: int,
        fitness_recommended_weeks: int,
    ) -> float:
        """
        Calculate starting mileage adjustment factor based on scenario.

        For "extra_time" scenario, reduce starting mileage to allow gradual build-up
        over the longer plan duration. For other scenarios, use base mileage.

        Args:
            scenario: Scenario type (TIME_CONSTRAINED, EXTRA_TIME, PERFECT_MATCH, NO_TIME_CONSTRAINT)
            base_weekly_mileage: Base weekly mileage from fitness assessment
            plan_length_weeks: Actual plan length in weeks
            fitness_recommended_weeks: Weeks needed based on fitness level

        Returns:
            Adjustment factor (1.0 = no adjustment, <1.0 = reduce, >1.0 = increase)
        """
        if scenario == self.EXTRA_TIME:
            # Calculate how much extra time we have
            extra_weeks = plan_length_weeks - fitness_recommended_weeks

            # For plans with significantly more time, start more conservatively
            # Reduce starting mileage by 10-20% depending on extra weeks
            # Example: 20 weeks available, 16 needed = 4 extra weeks = ~15% reduction
            if extra_weeks >= 4:
                # 4+ extra weeks: reduce by 20%
                adjustment = 0.80
            elif extra_weeks >= 2:
                # 2-3 extra weeks: reduce by 15%
                adjustment = 0.85
            else:
                # 1 extra week: reduce by 10%
                adjustment = 0.90

            logger.info(
                f"📉 Extra time scenario: Reducing starting mileage by {int((1 - adjustment) * 100)}% "
                f"({extra_weeks} extra weeks, plan_length={plan_length_weeks}, "
                f"fitness_recommended={fitness_recommended_weeks})"
            )
            return adjustment
        else:
            # No adjustment for other scenarios
            return 1.0

    def get_adjustments(
        self,
        fitness_recommended_weeks: int,
        available_weeks: Optional[int],
        base_weekly_mileage: float,
        plan_length_weeks: int,
    ) -> Dict[str, Any]:
        """
        Get all scenario-specific adjustments.

        Args:
            fitness_recommended_weeks: Weeks needed based on fitness level
            available_weeks: Weeks available between start and race date (None if no race date)
            base_weekly_mileage: Base weekly mileage from fitness assessment
            plan_length_weeks: Actual plan length in weeks

        Returns:
            Dict with scenario type and all adjustments:
            {
                "scenario": str,
                "starting_mileage_adjustment": float,
                ...
            }
        """
        scenario = self.determine_scenario(
            fitness_recommended_weeks=fitness_recommended_weeks,
            available_weeks=available_weeks,
        )

        starting_mileage_adjustment = self.get_starting_mileage_adjustment(
            scenario=scenario,
            base_weekly_mileage=base_weekly_mileage,
            plan_length_weeks=plan_length_weeks,
            fitness_recommended_weeks=fitness_recommended_weeks,
        )

        return {
            "scenario": scenario,
            "starting_mileage_adjustment": starting_mileage_adjustment,
        }

