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
from src.services.training_plan.v2.shared_v2.rounding_utils import whole_miles_half_up

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

    def _get_adjacent_training_days(
        self, training_days: List[str], long_run_day: str
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get the training days immediately before/after the long run.

        Uses TRAINING-DAYS adjacency (list-based), not calendar adjacency.
        This correctly handles cases where users don't train every day.

        Args:
            training_days: Ordered list of training days
            long_run_day: Which day is the long run

        Returns:
            Tuple of (day_before, day_after, two_days_after)
            Returns None for any day not in training_days
        """
        if not long_run_day or long_run_day not in training_days:
            return None, None, None

        long_idx = training_days.index(long_run_day)
        num_days = len(training_days)

        # Day immediately BEFORE long run (in training schedule order)
        day_before = training_days[long_idx - 1] if long_idx > 0 else training_days[-1]

        # Day immediately AFTER long run
        day_after = training_days[(long_idx + 1) % num_days]

        # Two days AFTER long run
        two_days_after = training_days[(long_idx + 2) % num_days]

        return day_before, day_after, two_days_after

    def _is_adjacent_by_training_schedule(
        self, dayA: str, dayB: str, training_days: List[str]
    ) -> bool:
        """
        Check if two days are adjacent in the training schedule.

        Uses TRAINING-DAYS adjacency (list-based), not calendar adjacency.
        This correctly handles cases where users don't train every day.

        Example:
            training_days = ["Mon", "Wed", "Fri", "Sat"]
            - Mon and Wed are adjacent (next in list)
            - Wed and Fri are adjacent
            - Fri and Sat are adjacent
            - Mon and Fri are NOT adjacent (skips Wed)

        Args:
            dayA: First day
            dayB: Second day
            training_days: Ordered list of training days

        Returns:
            True if days are adjacent in training schedule
        """
        if dayA not in training_days or dayB not in training_days:
            return False

        a_idx = training_days.index(dayA)
        b_idx = training_days.index(dayB)

        # Check if adjacent in list (wrapping around)
        num_days = len(training_days)
        diff = abs(a_idx - b_idx)
        return diff == 1 or diff == (num_days - 1)

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
        assert (
            len(training_days) == frequency
        ), f"training_days length {len(training_days)} != frequency {frequency}"
        assert (
            long_run_day in training_days
        ), f"long_run_day '{long_run_day}' not in training_days {training_days}"

        # 1. Get template for this race/frequency/phase/scenario
        template = get_template(
            race_type=self.race_type,
            frequency=frequency,
            phase=phase,
            scenario=self.scenario,
        )

        logger.debug(f"Template for {self.race_type}/{frequency}/{phase}: {template}")

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
            long_run_day=long_run_day,
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
        return ["easy" if is_quality_workout(w) else w for w in template]

    def _enforce_recovery_types(
        self,
        training_days: List[str],
        long_run_day: str,
        assigned: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Enforce that days before/after long run are 'easy' type.

        This is a CRITICAL safety rule: recovery days must be easy runs.
        Any quality workouts previously assigned to recovery days are
        redistributed to safe days.

        Args:
            training_days: Ordered list of training days
            long_run_day: Which day is the long run
            assigned: Current workout type assignments

        Returns:
            Updated assignments with recovery days forced to 'easy'
        """
        day_before_long, day_after_long, _ = self._get_adjacent_training_days(
            training_days, long_run_day
        )

        # Get all training days for redistribution logic
        non_long_days = [d for d in training_days if d != long_run_day]
        sorted_days = sorted(non_long_days)

        # Helper to find safe day for redistributed workout
        def find_safe_day_for_redistribution(
            removed_type: str, excluded_days: set
        ) -> Optional[str]:
            """Find a safe day to place a quality workout."""
            if not removed_type or not is_quality_workout(removed_type):
                return None

            for day in sorted_days:
                if day in excluded_days:
                    continue
                if day not in assigned or assigned[day] == "easy":
                    # Check not adjacent to long run or other recovery days
                    if not self._is_adjacent_by_training_schedule(
                        day, long_run_day, training_days
                    ):
                        if (
                            not day_after_long
                            or not self._is_adjacent_by_training_schedule(
                                day, day_after_long, training_days
                            )
                        ):
                            if (
                                not day_before_long
                                or not self._is_adjacent_by_training_schedule(
                                    day, day_before_long, training_days
                                )
                            ):
                                return day
            return None

        # Force day BEFORE long run to easy
        if day_before_long:
            if assigned.get(day_before_long) != "easy":
                removed_type = assigned.get(day_before_long)
                excluded = {day_before_long}
                if day_after_long:
                    excluded.add(day_after_long)
                safe_day = find_safe_day_for_redistribution(removed_type, excluded)
                if safe_day:
                    assigned[safe_day] = removed_type
                    logger.debug(
                        f"Redistributed {removed_type} from {day_before_long} "
                        f"(recovery day) to {safe_day}"
                    )
            assigned[day_before_long] = "easy"

        # Force day AFTER long run to easy
        if day_after_long:
            if assigned.get(day_after_long) != "easy":
                removed_type = assigned.get(day_after_long)
                excluded = {day_after_long}
                if day_before_long:
                    excluded.add(day_before_long)
                safe_day = find_safe_day_for_redistribution(removed_type, excluded)
                if safe_day:
                    assigned[safe_day] = removed_type
                    logger.debug(
                        f"Redistributed {removed_type} from {day_after_long} "
                        f"(recovery day) to {safe_day}"
                    )
            assigned[day_after_long] = "easy"

        return assigned

    def _map_to_days(
        self,
        template: List[str],
        training_days: List[str],
        long_run_day: str,
    ) -> Dict[str, str]:
        """
        Map template workout slots to actual training days.

        IMPROVED: Prevents back-to-back hard days by ensuring quality workouts
        are not placed on adjacent days.

        Strategy:
        1. Place long_run on long_run_day
        2. Sort remaining days by distance from long run
        3. Place quality workouts first:
           - Choose days furthest from long_run
           - Avoid adjacent quality days
           - Avoid adjacent to long run (if possible)
        4. Fill remaining days with easy/steady

        Args:
            template: Ordered list of workout types
            training_days: User's training days
            long_run_day: Which day gets the long run

        Returns:
            Dict mapping day_name -> workout_type
        """
        # Find long run index in training days
        long_idx = training_days.index(long_run_day)

        # Get non-long-run workouts from template
        non_long_template = [w for w in template if w != "long_run"]
        quality_workouts = [w for w in non_long_template if is_quality_workout(w)]
        non_quality_workouts = [
            w for w in non_long_template if not is_quality_workout(w)
        ]

        # Get non-long-run days
        non_long_days = [d for d in training_days if d != long_run_day]

        # Utility: circular distance from long run day
        def distance_from_long(day: str) -> int:
            idx = training_days.index(day)
            forward = (idx - long_idx) % len(training_days)
            backward = (long_idx - idx) % len(training_days)
            return min(forward, backward)

        # Sort days by distance from long run (furthest first)
        sorted_days = sorted(non_long_days, key=distance_from_long, reverse=True)

        # Initialize assignment with long run
        assigned: Dict[str, str] = {long_run_day: "long_run"}
        used_days: set = set()

        # -------------------------------------------------------
        # 1. Assign QUALITY WORKOUTS safely (prevents back-to-back)
        # -------------------------------------------------------
        def find_non_adjacent_pair(days: List[str], count: int) -> List[str]:
            """Find a set of days that are not adjacent to each other.
            Returns empty list if no valid non-adjacent combination exists."""
            if count <= 0:
                return []
            if count == 1:
                return [days[0]] if days else []
            if len(days) < count:
                return []

            # Try to find non-adjacent combinations
            from itertools import combinations

            for combo in combinations(days, count):
                # Check if any pair in combo is adjacent
                is_valid = True
                for i in range(len(combo)):
                    for j in range(i + 1, len(combo)):
                        if self._is_adjacent_by_training_schedule(
                            combo[i], combo[j], training_days
                        ):
                            is_valid = False
                            break
                    if not is_valid:
                        break
                if is_valid:
                    return list(combo)

            # No valid non-adjacent combination found
            return []

        # Day immediately before long run (in training_days order)
        day_before_long, _, _ = self._get_adjacent_training_days(
            training_days, long_run_day
        )

        # Filter out days adjacent to long run and immediately before long run
        safe_days = [
            d
            for d in sorted_days
            if not self._is_adjacent_by_training_schedule(
                d, long_run_day, training_days
            )
            and d != day_before_long
        ]

        # Find non-adjacent days for quality workouts
        quality_days = find_non_adjacent_pair(safe_days, len(quality_workouts))

        # If we couldn't find enough safe days, expand to include days adjacent to long run
        # (but still not immediately before)
        if len(quality_days) < len(quality_workouts):
            expanded_days = [d for d in sorted_days if d != day_before_long]
            quality_days = find_non_adjacent_pair(expanded_days, len(quality_workouts))

        # If STILL no valid placement (e.g., 4-day plan with all adjacent days),
        # reduce to 1 quality workout to ensure safe plan
        if len(quality_days) < len(quality_workouts):
            # Check if ANY non-adjacent pair exists
            all_adjacent = True
            for i in range(len(non_long_days)):
                for j in range(i + 1, len(non_long_days)):
                    if not self._is_adjacent_by_training_schedule(
                        non_long_days[i], non_long_days[j], training_days
                    ):
                        all_adjacent = False
                        break
                if not all_adjacent:
                    break

            if all_adjacent and len(quality_workouts) > 1:
                # Can't safely place 2 quality workouts - reduce to 1
                logger.info(
                    f"Reducing quality workouts from {len(quality_workouts)} to 1 "
                    f"(all {len(non_long_days)} non-long days are adjacent)"
                )
                quality_workouts = quality_workouts[:1]
                non_quality_workouts = [
                    "easy"
                ] + non_quality_workouts  # Add back as easy
                quality_days = [sorted_days[0]] if sorted_days else []

        # Assign quality workouts to selected days
        quality_assigned: List[str] = []
        for i, w in enumerate(quality_workouts):
            if i < len(quality_days):
                day = quality_days[i]
                assigned[day] = w
                used_days.add(day)
                quality_assigned.append(day)
            else:
                # Ultimate fallback: find any unused day
                for day in sorted_days:
                    if day not in used_days:
                        assigned[day] = w
                        used_days.add(day)
                        quality_assigned.append(day)
                        break

        # -------------------------------------------------------
        # 2. Fill remaining days with NON-QUALITY WORKOUTS
        # -------------------------------------------------------
        for w in non_quality_workouts:
            for day in sorted_days:
                if day not in used_days:
                    assigned[day] = w
                    used_days.add(day)
                    break

        # -------------------------------------------------------
        # 3. Fill leftovers with 'easy' (rare edge case)
        # -------------------------------------------------------
        for day in non_long_days:
            if day not in assigned:
                assigned[day] = "easy"

        # -------------------------------------------------------
        # 4. ENFORCE RECOVERY DAYS AROUND LONG RUN (CRITICAL SAFETY RULE)
        # -------------------------------------------------------
        assigned = self._enforce_recovery_types(training_days, long_run_day, assigned)

        return assigned

    def _allocate_non_recovery_day_miles(
        self,
        non_recovery_days: List[str],
        remaining_miles: float,
        day_to_type: Dict[str, str],
    ) -> Dict[str, float]:
        """Allocate initial miles to non-recovery days based on workout type shares."""
        # Calculate shares for non-recovery days only
        shares: Dict[str, float] = {}
        for day in non_recovery_days:
            workout_type = day_to_type[day]
            defn = get_workout_definition(workout_type)
            pct = defn.get("default_distribution_pct")
            shares[day] = pct if pct is not None else 0.15

        # Normalize shares
        total_share = sum(shares.values())
        if total_share > 0:
            shares = {d: s / total_share for d, s in shares.items()}
        else:
            equal_share = 1.0 / len(non_recovery_days) if non_recovery_days else 0
            shares = {d: equal_share for d in non_recovery_days}

        # Calculate miles
        day_miles: Dict[str, float] = {}
        for day in non_recovery_days:
            raw_miles = remaining_miles * shares[day]
            day_miles[day] = max(MIN_NON_LONG_MILES, round(raw_miles))

        return day_miles

    def _apply_non_long_run_caps(
        self,
        day_miles: Dict[str, float],
        non_long_days: List[str],
        recovery_days_set: set,
        long_run_day: str,
        MAX_NON_LONG_RUN_MILES: float = 10.0,
    ) -> Dict[str, float]:
        """
        Cap all non-long-run workouts at MAX_NON_LONG_RUN_MILES (default 10 miles).

        Recovery days are excluded as they have their own caps (4-6 miles).
        The long run day is excluded.

        This ensures mid-week runs never exceed the cap, even when weekly totals
        are high and share-based distribution would assign more.

        Args:
            day_miles: Current mileage assignments
            non_long_days: List of non-long-run training days
            recovery_days_set: Set of recovery days (excluded from cap)
            long_run_day: Long run day (excluded)
            MAX_NON_LONG_RUN_MILES: Maximum miles for any non-long-run workout

        Returns:
            Updated day_miles with caps applied and excess redistributed
        """
        capped_excess = 0.0
        days_that_were_capped = []

        for day in non_long_days:
            # Skip recovery days (they have their own caps)
            if day in recovery_days_set:
                continue

            if day in day_miles and day_miles[day] > MAX_NON_LONG_RUN_MILES:
                original_miles = day_miles[day]
                excess = original_miles - MAX_NON_LONG_RUN_MILES
                day_miles[day] = MAX_NON_LONG_RUN_MILES
                capped_excess += excess
                days_that_were_capped.append(day)
                logger.debug(
                    f"Capped non-long-run workout ({day}) from {original_miles:.1f}mi "
                    f"to {MAX_NON_LONG_RUN_MILES:.1f}mi (excess: {excess:.1f}mi)"
                )

        # Redistribute excess miles to other non-long-run, non-recovery days
        if capped_excess > 0:
            eligible_days = [
                d
                for d in non_long_days
                if d not in recovery_days_set
                and d not in days_that_were_capped
                and day_miles.get(d, 0) < MAX_NON_LONG_RUN_MILES
            ]

            if eligible_days:
                # Distribute excess proportionally to eligible days
                # Try to distribute evenly, but respect the cap
                excess_per_day = capped_excess / len(eligible_days)
                total_redistributed = 0.0

                for day in eligible_days:
                    current_miles = day_miles.get(day, 0)
                    new_miles = current_miles + excess_per_day
                    # Don't exceed the cap when redistributing
                    capped_new_miles = min(new_miles, MAX_NON_LONG_RUN_MILES)
                    added_miles = capped_new_miles - current_miles
                    day_miles[day] = capped_new_miles
                    total_redistributed += added_miles

                    if added_miles > 0.1:  # Only log if significant change
                        logger.debug(
                            f"Redistributed {added_miles:.1f}mi excess to {day} "
                            f"(now {capped_new_miles:.1f}mi)"
                        )

                # If there's still excess after redistribution (e.g., all days hit cap),
                # log a warning but don't adjust - this means the weekly total is very high
                remaining_excess = capped_excess - total_redistributed
                if remaining_excess > 0.1:
                    logger.debug(
                        f"Could not fully redistribute {remaining_excess:.1f}mi excess "
                        f"(all non-recovery days at or near {MAX_NON_LONG_RUN_MILES}mi cap)"
                    )
            else:
                logger.debug(
                    f"No eligible days for redistributing {capped_excess:.1f}mi excess "
                    f"(all non-recovery days already capped or excluded)"
                )

        return day_miles

    def _apply_recovery_caps(
        self,
        day_miles: Dict[str, float],
        day_before_long: Optional[str],
        day_after_long: Optional[str],
        two_days_after_long: Optional[str],
        RECOVERY_DAY_MAX_MILES: float,
        DAY_AFTER_LR_MAX_MILES: float,
        TWO_DAYS_AFTER_LR_MAX_MILES: float,
    ) -> Dict[str, float]:
        """Apply mileage caps to recovery days.

        Recovery days MUST be 4-6 miles (never more). This is a critical safety rule.
        """
        # Cap day BEFORE long run to 4-6 miles
        if day_before_long and day_before_long in day_miles:
            recovery_miles = day_miles[day_before_long]
            capped_miles = min(recovery_miles, RECOVERY_DAY_MAX_MILES)
            capped_miles = max(capped_miles, MIN_NON_LONG_MILES)

            # Warn if recovery day somehow exceeded cap (shouldn't happen)
            if recovery_miles > RECOVERY_DAY_MAX_MILES:
                logger.warning(
                    f"Recovery day ({day_before_long}) exceeded cap: {recovery_miles:.1f}mi > "
                    f"{RECOVERY_DAY_MAX_MILES:.1f}mi. Capping to {capped_miles:.1f}mi."
                )

            day_miles[day_before_long] = capped_miles
            if abs(recovery_miles - capped_miles) >= 0.1:  # Only log if changed
                logger.debug(
                    f"Capped day before long run ({day_before_long}) "
                    f"from {recovery_miles:.1f}mi to {capped_miles:.1f}mi"
                )

        # Cap day AFTER long run to 4-6 miles
        if day_after_long and day_after_long in day_miles:
            recovery_miles = day_miles[day_after_long]
            capped_miles = min(recovery_miles, DAY_AFTER_LR_MAX_MILES)
            capped_miles = max(capped_miles, MIN_NON_LONG_MILES)

            # Warn if recovery day somehow exceeded cap (shouldn't happen)
            if recovery_miles > DAY_AFTER_LR_MAX_MILES:
                logger.warning(
                    f"Recovery day ({day_after_long}) exceeded cap: {recovery_miles:.1f}mi > "
                    f"{DAY_AFTER_LR_MAX_MILES:.1f}mi. Capping to {capped_miles:.1f}mi."
                )

            day_miles[day_after_long] = capped_miles
            if abs(recovery_miles - capped_miles) >= 0.1:  # Only log if changed
                logger.debug(
                    f"Capped day after long run ({day_after_long}) "
                    f"from {recovery_miles:.1f}mi to {capped_miles:.1f}mi"
                )

        # Cap two days after long run to 7-8 miles max
        if two_days_after_long and two_days_after_long in day_miles:
            recovery_days_set = {d for d in [day_before_long, day_after_long] if d}
            if two_days_after_long not in recovery_days_set:
                current_miles = day_miles[two_days_after_long]
                capped_miles = min(current_miles, TWO_DAYS_AFTER_LR_MAX_MILES)
                day_miles[two_days_after_long] = capped_miles
                logger.debug(
                    f"Capped two days after long run ({two_days_after_long}) "
                    f"from {current_miles:.1f}mi to {capped_miles:.1f}mi"
                )

        return day_miles

    def _redistribute_remaining_miles(
        self,
        day_miles: Dict[str, float],
        remaining_miles: float,
        non_long_days: List[str],
        recovery_days_set: set,
        two_days_after_long: Optional[str],
        TWO_DAYS_AFTER_LR_MAX_MILES: float,
    ) -> Dict[str, float]:
        """Redistribute leftover miles to non-recovery days only.

        IMPORTANT: Recovery days are LOCKED and never adjusted - they must stay
        within their 4-6 mile caps regardless of weekly total.
        """
        assigned_non_long = sum(day_miles.values())
        diff = remaining_miles - assigned_non_long

        if abs(diff) >= 1 and non_long_days:
            # Get non-recovery days for redistribution (recovery days are fixed)
            non_recovery_days = [d for d in non_long_days if d not in recovery_days_set]

            if non_recovery_days:
                sorted_days = sorted(
                    non_recovery_days, key=lambda d: day_miles[d], reverse=True
                )
                adjustment = 1 if diff > 0 else -1
                MAX_NON_LONG_RUN_MILES = (
                    10.0  # General cap for all non-long-run workouts
                )
                for i in range(int(abs(diff))):
                    day = sorted_days[i % len(sorted_days)]
                    new_miles = day_miles[day] + adjustment
                    if new_miles >= MIN_NON_LONG_MILES:
                        # Don't exceed two-days-after cap if applicable
                        if (
                            day == two_days_after_long
                            and two_days_after_long not in recovery_days_set
                        ):
                            new_miles = min(new_miles, TWO_DAYS_AFTER_LR_MAX_MILES)
                        # Don't exceed general non-long-run cap (10 miles)
                        new_miles = min(new_miles, MAX_NON_LONG_RUN_MILES)
                        day_miles[day] = new_miles

            # Recovery days are LOCKED - never adjust them, even if it means
            # the weekly total doesn't match exactly. Safety rules override totals.
            final_total = sum(day_miles.values())
            final_diff = remaining_miles - final_total
            if abs(final_diff) >= 0.1:  # Allow small rounding differences
                logger.debug(
                    f"Weekly total adjustment: {final_diff:.1f}mi difference after "
                    f"redistribution (recovery days locked to caps). Weekly total is "
                    f"{final_total:.1f}mi instead of {remaining_miles:.1f}mi"
                )

        return day_miles

    def _distribute_mileage(
        self,
        day_to_type: Dict[str, str],
        training_days: List[str],
        weekly_mileage: float,
        long_run_miles: float,
        long_run_day: str = None,
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

        # -------------------------------------------------------
        # Identify recovery days FIRST (before calculating miles)
        # Uses training-days adjacency, not calendar adjacency
        # -------------------------------------------------------
        RECOVERY_DAY_MAX_MILES = 6.0
        DAY_AFTER_LR_MAX_MILES = 6.0
        TWO_DAYS_AFTER_LR_MAX_MILES = 8.0

        day_before_long, day_after_long, two_days_after_long = (
            self._get_adjacent_training_days(training_days, long_run_day or "")
        )

        # Set recovery days to target range (4-5 miles) BEFORE calculating shares
        recovery_days_set = {
            d for d in [day_before_long, day_after_long] if d is not None
        }
        recovery_day_target = 5.0  # Target 5 miles for recovery days (range 4-6)

        day_miles: Dict[str, float] = {}

        # Reserve target miles for recovery days first
        recovery_miles_reserved = 0
        for day in recovery_days_set:
            if day in non_long_days:
                day_miles[day] = recovery_day_target
                recovery_miles_reserved += recovery_day_target

        # Calculate remaining miles for non-recovery days
        remaining_after_recovery = remaining_miles - recovery_miles_reserved
        non_recovery_days_for_shares = [
            d for d in non_long_days if d not in recovery_days_set
        ]

        # Allocate miles to non-recovery days using helper
        non_recovery_miles = self._allocate_non_recovery_day_miles(
            non_recovery_days_for_shares,
            remaining_after_recovery,
            day_to_type,
        )
        day_miles.update(non_recovery_miles)

        # Apply general cap for all non-long-run workouts (10 miles max)
        # This ensures mid-week runs never exceed 10 miles, even in high-volume weeks
        MAX_NON_LONG_RUN_MILES = 10.0
        day_miles = self._apply_non_long_run_caps(
            day_miles,
            non_long_days,
            recovery_days_set,
            long_run_day or "",
            MAX_NON_LONG_RUN_MILES,
        )

        # Apply recovery day caps using helper
        day_miles = self._apply_recovery_caps(
            day_miles,
            day_before_long,
            day_after_long,
            two_days_after_long,
            RECOVERY_DAY_MAX_MILES,
            DAY_AFTER_LR_MAX_MILES,
            TWO_DAYS_AFTER_LR_MAX_MILES,
        )

        # Redistribute remaining miles using helper
        day_miles = self._redistribute_remaining_miles(
            day_miles,
            remaining_miles,
            non_long_days,
            recovery_days_set,
            two_days_after_long,
            TWO_DAYS_AFTER_LR_MAX_MILES,
        )

        # Re-apply caps as final safeguard (ensures they're never exceeded)
        # This is critical because redistribution might have affected other days
        MAX_NON_LONG_RUN_MILES = 10.0

        # Re-apply non-long-run caps first
        day_miles = self._apply_non_long_run_caps(
            day_miles,
            non_long_days,
            recovery_days_set,
            long_run_day or "",
            MAX_NON_LONG_RUN_MILES,
        )

        # Re-apply recovery caps (recovery days must ALWAYS stay within 4-6 mile limits)
        day_miles = self._apply_recovery_caps(
            day_miles,
            day_before_long,
            day_after_long,
            two_days_after_long,
            RECOVERY_DAY_MAX_MILES,
            DAY_AFTER_LR_MAX_MILES,
            TWO_DAYS_AFTER_LR_MAX_MILES,
        )

        # Build final assignments
        result: Dict[str, Dict[str, Any]] = {}

        for day in training_days:
            workout_type = day_to_type[day]
            defn = get_workout_definition(workout_type)

            if workout_type == "long_run":
                miles = long_run_miles
            else:
                miles = day_miles.get(day, MIN_NON_LONG_MILES)

            # Use capitalized workout type as label (e.g., "Easy", "Tempo", "Long")
            if workout_type == "long_run":
                short_label = "Long"
            else:
                short_label = workout_type.capitalize()

            result[day] = {
                "day": day,
                "type": workout_type,
                "miles": whole_miles_half_up(miles),
                "distance_miles": float(miles),
                "label": short_label,
                "workout_type": short_label,
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
