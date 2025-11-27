"""
Workout Placement Engine - Central Logic for Step 6
====================================================

PURPOSE
-------
This is the CENTRAL ENGINE that combines:
- Workout definitions (what workouts exist)
- Weekly templates (which workouts go in which phase)
- Placement rules (safety and quality constraints)

Into a final day-by-day workout assignment with mileage distribution.

This is the ONLY place where workout placement logic should live.
Step 6 in the orchestrator should simply call this engine.

RESPONSIBILITIES
----------------
1. Look up the correct template for race/frequency/phase/scenario
2. Apply cutback week simplification if needed
3. Map template slots to actual training days
4. Distribute mileage across workouts
5. Validate placement against rules
6. Return complete workout assignments

INPUTS (from Step 5)
--------------------
- weekly_mileage: Total miles for the week
- long_run_miles: Long run distance
- phase: Training phase (Base/Build/Peak/Taper)
- is_cutback: Whether this is a recovery week

INPUTS (from user/config)
-------------------------
- race_type: marathon/half/10k/5k
- frequency: Training days per week (3-6)
- training_days: Actual day names (e.g., ["Tue", "Thu", "Sat", "Sun"])
- long_run_day: Which day is the long run
- scenario: Optional scenario override

OUTPUTS
-------
Dict mapping day_name -> {
    "type": workout type key
    "miles": distance in miles
    "label": human-readable name
    "pace_guidance": pace instruction
    "is_quality": whether this is a hard workout
    "intensity": intensity level
    "description": workout description
}

INVARIANTS (DO NOT VIOLATE)
---------------------------
1. Output must include all training_days
2. Long run day must have type="long_run"
3. Total miles must equal weekly_mileage (within rounding)
4. Each non-long workout must have at least MIN_NON_LONG_MILES

Author: SmartCoach Development Team
Last Updated: November 2025
"""

from typing import Dict, List, Any, Optional
import logging

from .workout_definitions import (
    WORKOUT_DEFINITIONS,
    is_quality_workout,
    get_workout_definition,
)
from .weekly_templates import get_template
from .placement_rules import get_rules, validate_placement

logger = logging.getLogger(__name__)

# Minimum miles for any non-long-run workout
MIN_NON_LONG_MILES = 3.0


class WorkoutPlacementEngine:
    """
    Central engine for placing workouts on training days.
    
    This class encapsulates all workout placement logic and should be
    the single point of entry for Step 6 in the plan generation pipeline.
    
    Usage:
        engine = WorkoutPlacementEngine(race_type="marathon", scenario="injury_safe")
        assignments = engine.place_workouts(
            frequency=4,
            phase="Build",
            training_days=["Tue", "Thu", "Sat", "Sun"],
            weekly_mileage=40.0,
            long_run_miles=14.0,
            long_run_day="Sat",
            is_cutback=False,
        )
    """
    
    def __init__(
        self,
        race_type: str = "marathon",
        scenario: Optional[str] = None,
    ):
        """
        Initialize the placement engine.
        
        Args:
            race_type: Race distance ("marathon", "half", "10k", "5k")
            scenario: Optional scenario for rule/template overrides
        """
        self.race_type = race_type
        self.scenario = scenario
        self.rules = get_rules(scenario)
    
    def place_workouts(
        self,
        frequency: int,
        phase: str,
        training_days: List[str],
        weekly_mileage: float,
        long_run_miles: float,
        long_run_day: str = "Sat",
        is_cutback: bool = False,
        weeks_until_race: Optional[int] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Place workouts on training days for a single week.
        
        This is the main entry point for Step 6.
        
        Args:
            frequency: Number of training days (3-6)
            phase: Training phase ("Base", "Build", "Peak", "Taper")
            training_days: Ordered list of day names
            weekly_mileage: Total weekly mileage from Step 5
            long_run_miles: Long run distance from Step 5
            long_run_day: Which day is the long run
            is_cutback: Whether this is a cutback/recovery week
            weeks_until_race: Weeks remaining until race (for taper rules)
            
        Returns:
            Dict mapping day_name -> workout assignment
        """
        # Validate inputs
        assert len(training_days) == frequency, (
            f"training_days length {len(training_days)} != frequency {frequency}"
        )
        assert long_run_day in training_days, (
            f"long_run_day '{long_run_day}' not in training_days {training_days}"
        )
        
        # 1. Get template for this race/frequency/phase/scenario
        template = get_template(
            race_type=self.race_type,
            frequency=frequency,
            phase=phase,
            scenario=self.scenario,
        )
        
        logger.debug(
            f"Template for {self.race_type}/{frequency}/{phase}: {template}"
        )
        
        # 2. If cutback week, simplify template (remove quality)
        if is_cutback and self.rules.get("avoid_quality_during_cutback", True):
            template = self._simplify_for_cutback(template)
            logger.debug(f"Simplified for cutback: {template}")
        
        # 3. Map template slots to actual days
        day_to_type = self._map_to_days(template, training_days, long_run_day)
        
        logger.debug(f"Day mapping: {day_to_type}")
        
        # 4. Distribute mileage
        assignments = self._distribute_mileage(
            day_to_type=day_to_type,
            training_days=training_days,
            weekly_mileage=weekly_mileage,
            long_run_miles=long_run_miles,
        )
        
        # 5. Validate placement
        workout_list = [day_to_type[d] for d in training_days]
        validation_result = validate_placement(
            workouts=workout_list,
            days=training_days,
            phase=phase,
            is_cutback=is_cutback,
            rules=self.rules,
            weeks_until_race=weeks_until_race,
        )
        
        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])
        
        # BLOCK on safety errors - these are dangerous
        if errors:
            error_msg = "; ".join(errors)
            logger.error(f"Safety violation in week placement: {error_msg}")
            raise ValueError(f"Unsafe workout placement: {error_msg}")
        
        # Log warnings at DEBUG level only - informational, not user-facing
        if warnings:
            for w in warnings:
                logger.debug(f"Placement quality note: {w}")
        
        return assignments
    
    def _simplify_for_cutback(self, template: List[str]) -> List[str]:
        """
        Replace quality workouts with easy for cutback weeks.
        
        Cutback weeks should focus on recovery, not intensity.
        This maintains the template structure but removes hard efforts.
        
        Args:
            template: Original workout template
            
        Returns:
            Simplified template with quality workouts replaced by easy
        """
        return [
            "easy" if is_quality_workout(w) else w
            for w in template
        ]
    
    def _map_to_days(
        self,
        template: List[str],
        training_days: List[str],
        long_run_day: str,
    ) -> Dict[str, str]:
        """
        Map template workout slots to actual training days.
        
        The template is an ordered list ending with "long_run".
        We need to map this to the user's actual training days,
        ensuring the long_run lands on the correct day.
        
        Strategy:
        1. Place long_run on long_run_day
        2. Distribute remaining workouts to other days
        3. Prioritize placing quality workouts away from long run
        
        Args:
            template: Ordered list of workout types
            training_days: User's training days
            long_run_day: Which day gets the long run
            
        Returns:
            Dict mapping day_name -> workout_type
        """
        # Find long run index in training days
        long_idx = training_days.index(long_run_day)
        
        # Get non-long-run workouts from template (all but last)
        non_long_template = [w for w in template if w != "long_run"]
        
        # Get non-long-run days
        non_long_days = [d for d in training_days if d != long_run_day]
        
        # Build mapping
        day_to_type: Dict[str, str] = {}
        
        # Place long run
        day_to_type[long_run_day] = "long_run"
        
        # Place remaining workouts
        # Strategy: quality workouts go on days furthest from long run
        # Easy workouts go on days closest to long run
        
        # Sort non-long days by distance from long run (furthest first)
        def distance_from_long(day: str) -> int:
            day_idx = training_days.index(day)
            # Circular distance
            forward = (long_idx - day_idx) % len(training_days)
            backward = (day_idx - long_idx) % len(training_days)
            return min(forward, backward)
        
        # Separate quality and non-quality workouts
        quality_workouts = [w for w in non_long_template if is_quality_workout(w)]
        non_quality_workouts = [w for w in non_long_template if not is_quality_workout(w)]
        
        # Sort days: furthest from long run first (for quality workouts)
        sorted_days = sorted(non_long_days, key=distance_from_long, reverse=True)
        
        # Assign quality workouts to furthest days
        for i, workout in enumerate(quality_workouts):
            if i < len(sorted_days):
                day_to_type[sorted_days[i]] = workout
        
        # Assign non-quality workouts to remaining days
        remaining_days = [d for d in sorted_days if d not in day_to_type]
        for i, workout in enumerate(non_quality_workouts):
            if i < len(remaining_days):
                day_to_type[remaining_days[i]] = workout
        
        # Fill any remaining days with "easy"
        for day in training_days:
            if day not in day_to_type:
                day_to_type[day] = "easy"
        
        return day_to_type
    
    def _distribute_mileage(
        self,
        day_to_type: Dict[str, str],
        training_days: List[str],
        weekly_mileage: float,
        long_run_miles: float,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Distribute mileage across workouts based on type.
        
        Mileage distribution strategy:
        1. Long run gets its assigned miles
        2. Remaining miles distributed based on workout type percentages
        3. Ensure minimum miles per non-long workout
        4. Round to whole miles
        
        Args:
            day_to_type: Mapping of day -> workout type
            training_days: Ordered list of days
            weekly_mileage: Total weekly mileage
            long_run_miles: Long run distance
            
        Returns:
            Dict mapping day -> complete workout assignment
        """
        remaining_miles = weekly_mileage - long_run_miles
        non_long_days = [d for d in training_days if day_to_type[d] != "long_run"]
        
        # Calculate shares based on workout type
        shares: Dict[str, float] = {}
        for day in non_long_days:
            workout_type = day_to_type[day]
            defn = get_workout_definition(workout_type)
            pct = defn.get("default_distribution_pct")
            
            if pct is not None:
                shares[day] = pct
            else:
                # Default share for easy/unspecified
                shares[day] = 0.15
        
        # Normalize shares to sum to 1.0
        total_share = sum(shares.values())
        if total_share > 0:
            shares = {d: s / total_share for d, s in shares.items()}
        else:
            # Equal distribution if no shares defined
            equal_share = 1.0 / len(non_long_days) if non_long_days else 0
            shares = {d: equal_share for d in non_long_days}
        
        # Calculate initial miles per day
        day_miles: Dict[str, float] = {}
        for day in non_long_days:
            raw_miles = remaining_miles * shares[day]
            day_miles[day] = max(MIN_NON_LONG_MILES, round(raw_miles))
        
        # Adjust to match total (handle rounding)
        assigned_non_long = sum(day_miles.values())
        diff = remaining_miles - assigned_non_long
        
        if abs(diff) >= 1 and non_long_days:
            # Distribute difference to largest workout(s)
            sorted_days = sorted(non_long_days, key=lambda d: day_miles[d], reverse=True)
            adjustment = 1 if diff > 0 else -1
            for i in range(int(abs(diff))):
                day = sorted_days[i % len(sorted_days)]
                new_miles = day_miles[day] + adjustment
                if new_miles >= MIN_NON_LONG_MILES:
                    day_miles[day] = new_miles
        
        # Build final assignments
        result: Dict[str, Dict[str, Any]] = {}
        
        for day in training_days:
            workout_type = day_to_type[day]
            defn = get_workout_definition(workout_type)
            
            if workout_type == "long_run":
                miles = long_run_miles
            else:
                miles = day_miles.get(day, MIN_NON_LONG_MILES)
            
            result[day] = {
                "day": day,
                "type": workout_type,
                "miles": int(round(miles)),
                "distance_miles": float(miles),
                "label": defn.get("description", workout_type),
                "workout_type": defn.get("description", workout_type),
                "pace_guidance": defn.get("pace_guidance", "Easy"),
                "is_quality": defn.get("is_quality", False),
                "intensity": defn.get("intensity", "easy"),
                "workout_description": defn.get("description", ""),
            }
        
        return result
    
    def get_template_for_week(
        self,
        frequency: int,
        phase: str,
        is_cutback: bool = False,
    ) -> List[str]:
        """
        Get the raw template for a week (for debugging/display).
        
        Args:
            frequency: Training days per week
            phase: Training phase
            is_cutback: Whether this is a cutback week
            
        Returns:
            List of workout types
        """
        template = get_template(
            race_type=self.race_type,
            frequency=frequency,
            phase=phase,
            scenario=self.scenario,
        )
        
        if is_cutback and self.rules.get("avoid_quality_during_cutback", True):
            template = self._simplify_for_cutback(template)
        
        return template

