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
        use_new_engine: bool = True,  # Kept for compatibility, always True now
    ):
        """Initialize Pass 3 workout distribution calculator.
        
        Args:
            config: Race distance configuration
            race_type: Race type for template lookup ("marathon", "half", etc.)
            scenario: Optional scenario for template/rule overrides
            use_new_engine: Deprecated - always uses new engine
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
    ) -> Dict[str, Any]:
        """Distribute workouts across training days for each week.

        Args:
            skel_long: List of weeks with week_number, phase, long_run_miles, weekly_mileage
            training_days: List of training days (e.g., ["Mon", "Wed", "Thu", "Sat"])
            total_weeks: Total weeks in plan (for calculating weeks_until_race)

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

        # Determine long run day (prefer Sat, then Sun, else last day)
        long_run_day = None
        if DAY_NAMES_ABBREV[5] in training_days:  # Saturday
            long_run_day = DAY_NAMES_ABBREV[5]
        elif DAY_NAMES_ABBREV[6] in training_days:  # Sunday
            long_run_day = DAY_NAMES_ABBREV[6]
        else:
            long_run_day = training_days[-1]  # Default to last day

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
            workouts = []
            for day in training_days:
                if day in schedule:
                    workout_data = schedule[day].copy()
                    workouts.append(workout_data)
            
            logger.debug(
                f"Week {week_num} ({phase}): Distributed {len(workouts)} workouts "
                f"using template-based placement"
            )

            # Verify total matches (sanity check) - log at debug level only
            workout_sum = sum(
                wk.get("distance_miles", wk.get("miles", 0)) for wk in workouts
            )
            if abs(workout_sum - weekly_total) > 0.1:
                logger.debug(
                    f"Week {week_num}: Workout sum {workout_sum} ≠ weekly_total {weekly_total} "
                    f"(rounding variance, not user-facing)"
                )

            weeks_out.append(
                {
                    "week_number": week_num,
                    "phase": phase,
                    "weekly_mileage": weekly_total,
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
