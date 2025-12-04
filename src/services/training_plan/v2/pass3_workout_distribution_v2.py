"""
Pass 3 (Step 6): Workout Distribution Service
==============================================

PURPOSE
-------
Distribute workouts across training days using the WorkoutPlacementEngine
from the workout_taxonomy module. This provides phase-aware, template-based
workout distribution.

RESPONSIBILITIES
----------------
- Take weekly skeleton (long_run_miles, weekly_mileage, phase) from Step 5
- Use WorkoutPlacementEngine to assign workouts to training days
- Apply phase-aware templates (Base/Build/Peak/Taper)
- Apply scenario-specific overrides if applicable
- Return weekly workout distributions

DESIGN
------
- Deterministic (no LLM calls)
- Phase-aware (different templates per phase)
- Scenario-aware (injury_safe, time_constrained, etc.)
- Uses global workout_taxonomy for consistency

Author: SmartCoach Development Team
Last Updated: November 2025
"""

from typing import Any, Dict, List
import logging

from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig
from src.services.training_plan.workout_utils import (
    calculate_weekly_mileage_from_workouts,
)
from src.services.training_plan.v2.shared_v2.rounding_utils import (
    round_workout_distance,
)

logger = logging.getLogger(__name__)


class Pass3WorkoutDistribution:
    """Pass 3 (Step 6) - Distribute workouts across training days.

    Uses the WorkoutPlacementEngine from workout_taxonomy for phase-aware,
    template-based workout distribution.
    """

    def __init__(
        self,
        config: RaceDistanceConfig,
        race_type: str = "marathon",
        scenario: str = None,
    ):
        """Initialize Pass 3 workout distribution calculator.

        Args:
            config: Race distance configuration
            race_type: Race type for template lookup ("marathon", "half", etc.)
            scenario: Optional scenario for template/rule overrides
        """
        self.config = config
        self.race_type = race_type
        self.scenario = scenario

        # Initialize placement engine from workout_taxonomy
        from src.services.training_plan.v2.workout_taxonomy import (
            WorkoutPlacementEngine,
        )

        self.placement_engine = WorkoutPlacementEngine(
            race_type=race_type,
            scenario=scenario,
        )

    def run(
        self,
        skel_long: List[Dict[str, Any]],
        training_days: List[str],
        total_weeks: int = None,
        long_run_day: str = None,
        unit_system: str = "imperial",
    ) -> Dict[str, Any]:
        """Distribute workouts across training days for each week.

        Args:
            skel_long: List of weeks with week_number, phase, long_run_miles, weekly_mileage
            training_days: List of training days (e.g., ["Mon", "Wed", "Thu", "Sat"])
            total_weeks: Total weeks in plan (for calculating weeks_until_race)
            long_run_day: Preferred day for long runs (if None, auto-selects)
            unit_system: Deprecated - kept for backward compatibility. All rounding is now in miles.

        Returns:
            Dict with "weeks" list containing workout distributions
        """
        from src.utils.date_helpers import DEFAULT_TRAINING_DAYS, DAY_NAMES_ABBREV

        if not training_days:
            training_days = DEFAULT_TRAINING_DAYS

        runs_per_week = len(training_days)

        if runs_per_week not in (3, 4, 5, 6):
            logger.warning(
                f"runs_per_week={runs_per_week} not in (3,4,5,6), defaulting to 4"
            )
            runs_per_week = 4
            training_days = DEFAULT_TRAINING_DAYS

        # Determine long run day (use provided, or auto-select)
        if long_run_day is None:
            # Auto-select (prefer Sat, then Sun, else last day)
            if DAY_NAMES_ABBREV[5] in training_days:  # Saturday
                long_run_day = DAY_NAMES_ABBREV[5]
            elif DAY_NAMES_ABBREV[6] in training_days:  # Sunday
                long_run_day = DAY_NAMES_ABBREV[6]
            else:
                long_run_day = training_days[-1]  # Default to last day

        # Validate that long_run_day is in training_days (safety check)
        if long_run_day not in training_days:
            logger.warning(
                f"long_run_day '{long_run_day}' not in training_days {training_days}, "
                f"defaulting to last day"
            )
            long_run_day = training_days[-1]

        weeks_out: List[Dict[str, Any]] = []
        total_plan_weeks = total_weeks or len(skel_long)

        for w in skel_long:
            week_num = int(w.get("week_number", len(weeks_out) + 1))
            long_run = float(w.get("long_run_miles", 0) or 0)
            weekly_total = float(w.get("weekly_mileage", 0) or 0)
            phase = w.get("phase", "Build")
            is_cutback = w.get("is_cutback", False)

            # Calculate weeks until race (for taper rules)
            weeks_until_race = total_plan_weeks - week_num

            # Use WorkoutPlacementEngine for phase-aware distribution
            schedule = self.placement_engine.place_workouts(
                frequency=runs_per_week,
                phase=phase,
                training_days=training_days,
                weekly_mileage=weekly_total,
                long_run_miles=long_run,
                long_run_day=long_run_day,
                is_cutback=is_cutback,
                weeks_until_race=weeks_until_race,
            )

            # Convert to list format for backward compatibility
            # Round individual workout distances to practical increments based on unit system
            workouts = []
            for day in training_days:
                if day in schedule:
                    workout_data = schedule[day].copy()
                    # Round distance_miles to practical increments (0.5 miles)
                    # Frontend will convert to km for display using toDisplayDistance()
                    if "distance_miles" in workout_data:
                        original_distance = workout_data.get("distance_miles", 0)
                        if original_distance > 0:
                            workout_data["distance_miles"] = round_workout_distance(
                                original_distance
                            )
                    # Also handle "miles" field if present
                    if "miles" in workout_data:
                        original_distance = workout_data.get("miles", 0)
                        if original_distance > 0:
                            workout_data["miles"] = round_workout_distance(
                                original_distance
                            )
                    workouts.append(workout_data)

            logger.debug(
                f"Week {week_num} ({phase}): Distributed {len(workouts)} workouts "
                f"using template-based placement"
            )

            # Calculate actual weekly mileage from workout distances
            # This ensures the displayed total matches what users see in daily columns
            # After caps/redistribution, the actual sum may differ from the target
            actual_weekly_mileage = calculate_weekly_mileage_from_workouts(workouts)

            # Log if there's a significant difference from target (for debugging)
            if abs(actual_weekly_mileage - weekly_total) > 0.5:
                logger.debug(
                    f"Week {week_num}: Actual sum {actual_weekly_mileage} ≠ target {weekly_total} "
                    f"(due to recovery caps and non-long-run caps, this is expected)"
                )

            weeks_out.append(
                {
                    "week_number": week_num,
                    "phase": phase,
                    "weekly_mileage": actual_weekly_mileage,  # Use actual sum, not target
                    "long_run_miles": long_run,
                    "workouts": workouts,
                    "is_cutback": is_cutback,
                }
            )

        logger.info(
            f"Pass3 (Step 6) generated {len(weeks_out)} weeks using "
            f"WorkoutPlacementEngine (race_type={self.race_type}, scenario={self.scenario})"
        )
        return {"weeks": weeks_out}
