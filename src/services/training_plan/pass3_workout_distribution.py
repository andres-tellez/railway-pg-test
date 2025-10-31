"""
Pass 3: Workout Distribution Service

Purpose:
    Distribute remaining weekly mileage across non-long-run days using
    run-type percentages. This is a deterministic calculation that does NOT
    modify long_run_miles or weekly_mileage values.

Responsibilities:
    - Take long_run_miles, total_weekly_miles, and runs_per_week as inputs
    - Calculate non-long-run total mileage
    - Distribute remaining mileage using run-type percentages based on runs/week
    - Assign workout types (Medium, Easy, Tempo, etc.) to appropriate days
    - Ensure minimum 3 miles per non-long run
    - Handle rounding to match total_weekly_miles exactly

Design:
    - Deterministic (no LLM calls)
    - Preserves long_run_miles and weekly_mileage (read-only)
    - Uses percentage-based distribution for realistic run types

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from typing import Any, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

# Constants
MIN_EASY_MILES = 3

# Run type distribution by frequency
RUN_TYPE_DISTRIBUTION = {
    3: ["Medium", "Easy"],
    4: ["Medium", "Easy", "Easy/Tempo"],
    5: ["Medium", "Easy", "Tempo", "Easy"],
}

# Percentage of non-long-run mileage to allocate per run type
NON_LONG_RUN_PCT = {
    3: [0.55, 0.45],  # 2 other days: medium, easy
    4: [0.40, 0.30, 0.30],  # 3 other days: medium, easy, easy/tempo
    5: [0.32, 0.25, 0.23, 0.20],  # 4 other days: medium, easy, tempo, easy
}


def round_to_whole(x: float) -> int:
    """Round to nearest whole number."""
    return int(round(x))


def calculate_workout_distribution(
    long_run_miles: float,
    total_weekly_miles: float,
    runs_per_week: int,
    training_days: List[str],
) -> List[Dict[str, Any]]:
    """Calculate workout distribution for a single week.

    Args:
        long_run_miles: Long run distance (fixed, not modified)
        total_weekly_miles: Total weekly mileage (fixed, not modified)
        runs_per_week: Total run days including long run day (3, 4, or 5)
        training_days: List of training days (e.g., ["Mon", "Wed", "Thu", "Sat"])

    Returns:
        List of workout dicts with day, workout_type, distance_miles, etc.
    """
    if runs_per_week not in (3, 4, 5):
        raise ValueError(f"runs_per_week must be 3, 4, or 5, got {runs_per_week}")

    # Step 1: Calculate non-long-run total
    non_long_total = max(0.0, total_weekly_miles - long_run_miles)

    # Step 2: Determine run types
    run_types = RUN_TYPE_DISTRIBUTION[runs_per_week]
    non_long_pcts = NON_LONG_RUN_PCT[runs_per_week]

    # Step 3: Assign mileage using percentages
    non_long_distances = [non_long_total * pct for pct in non_long_pcts]

    # Step 4: Round to whole miles and ensure minimums
    rounded = [round_to_whole(d) for d in non_long_distances]

    # Ensure each non-long run ≥ MIN_EASY_MILES
    for i in range(len(rounded)):
        if rounded[i] < MIN_EASY_MILES:
            rounded[i] = MIN_EASY_MILES

    # Step 5: Adjust rounding error so total = total_weekly_miles
    current_total = long_run_miles + sum(rounded)
    drift = round_to_whole(total_weekly_miles) - current_total

    # Distribute drift across non-long runs (prefer larger runs first)
    if drift != 0:
        # Sort indices by distance (largest first) for drift distribution
        indices = sorted(range(len(rounded)), key=lambda i: rounded[i], reverse=True)
        step = 1 if drift > 0 else -1

        while drift != 0 and indices:
            for idx in indices:
                if step < 0 and rounded[idx] <= MIN_EASY_MILES:
                    # Don't go below minimum
                    continue
                rounded[idx] += step
                drift -= step
                if drift == 0:
                    break

    # Step 6: Assign workouts to days with recovery-aware ordering
    days_order = [
        d
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if d in training_days
    ] or ["Mon", "Wed", "Thu", "Sat"]

    # Place long run on weekend (prefer Sat, then Sun)
    if "Sat" in days_order:
        long_day = "Sat"
    elif "Sun" in days_order:
        long_day = "Sun"
    else:
        long_day = days_order[-1]

    # Get non-long-run days in order
    non_long_days = [d for d in days_order if d != long_day]

    # Step 6a: Sort distances from shortest to longest (recovery-aware)
    # The first weekday after the long run should be the shortest (recovery day)
    sorted_distances = sorted(rounded)  # Shortest to longest

    # Step 6b: Order non-long-run days by position relative to long run
    # Pattern: Long Run (Saturday) → Recovery (Monday, shortest) → Medium (Wednesday) → Longer (Thursday, longest)
    week_day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Find the index of the long run day in the week
    try:
        long_day_idx = week_day_order.index(long_day)
    except ValueError:
        long_day_idx = 5  # Default to Saturday

    # Calculate "forward position" for each non-long-run day (how many days forward from long run)
    # This determines the order: closest forward day = shortest run, furthest forward = longest run
    day_position_map: List[Tuple[str, float, int]] = (
        []
    )  # (day, distance, forward_position)

    for day in non_long_days:
        try:
            day_idx = week_day_order.index(day)
            # Calculate forward position (days ahead in the week cycle)
            # If day comes before long run in the week order, it's in the next cycle
            if day_idx > long_day_idx:
                forward_position = day_idx - long_day_idx  # Same week, after long run
            else:
                # Day is in next cycle (e.g., Monday after Saturday)
                forward_position = (7 - long_day_idx) + day_idx
        except ValueError:
            forward_position = 7  # Default: treat as far away

        day_position_map.append((day, 0.0, forward_position))

    # Sort by forward position (closest forward = shortest run, furthest forward = longest run)
    day_position_map.sort(key=lambda x: x[2])  # Sort by forward_position ascending

    # Assign distances recovery-aware but with previous ordering:
    # Shortest → first day after LR, then increasing so that Thu is the longest weekday.
    # This restores Mon < Wed < Thu behavior from the snapshot.
    for i, (day, _, forward_pos) in enumerate(day_position_map):
        # sorted_distances is already shortest→longest; assign in order
        assigned = (
            sorted_distances[i] if i < len(sorted_distances) else sorted_distances[-1]
        )
        day_position_map[i] = (day, assigned, forward_pos)

    # Post-process to ensure strict progression (recovery day strictly shorter)
    if len(day_position_map) >= 2:
        # Ensure the first day (recovery day) is strictly shorter than the second day
        first_day, first_dist, first_pos = day_position_map[0]
        second_day, second_dist, second_pos = day_position_map[1]

        if first_dist >= second_dist:
            # Recovery day is not shorter - adjust by taking 1 mile from recovery
            # and adding it to a later day (prefer the last/longest day)
            if first_dist > MIN_EASY_MILES:
                # Reduce recovery day by 1 mile (but keep at minimum)
                new_first_dist = max(MIN_EASY_MILES, first_dist - 1.0)
                reduction = first_dist - new_first_dist

                # Find the day furthest from long run (last in sorted list) and add the reduction
                if len(day_position_map) > 1:
                    last_day, last_dist, last_pos = day_position_map[-1]
                    day_position_map[-1] = (last_day, last_dist + reduction, last_pos)
                    day_position_map[0] = (first_day, new_first_dist, first_pos)

        # Ensure progression across all days (each day should be >= previous + 1.0 miles for noticeable progression)
        # This creates: recovery < mid-week < longest (with clear increases)
        MIN_PROGRESSION = 1.0  # Minimum difference between consecutive days (make progression noticeable)
        for i in range(1, len(day_position_map)):
            prev_day, prev_dist, prev_pos = day_position_map[i - 1]
            curr_day, curr_dist, curr_pos = day_position_map[i]

            if curr_dist <= prev_dist:
                # Current day is not longer - adjust by taking from previous or adding to current
                diff = prev_dist - curr_dist + MIN_PROGRESSION
                # Try to take from previous (if above minimum)
                if prev_dist - diff >= MIN_EASY_MILES:
                    day_position_map[i - 1] = (prev_day, prev_dist - diff, prev_pos)
                    day_position_map[i] = (curr_day, curr_dist + diff, curr_pos)
                else:
                    # Can't reduce previous enough, add to current
                    day_position_map[i] = (
                        curr_day,
                        prev_dist + MIN_PROGRESSION,
                        curr_pos,
                    )

        # Re-balance to ensure total still matches after adjustments
        # Calculate current total and adjust if needed
        current_non_long_total = sum(dist for _, dist, _ in day_position_map)
        target_non_long_total = non_long_total

        if abs(current_non_long_total - target_non_long_total) > 0.1:
            # Adjust by adding/subtracting from the longest day (furthest from long run)
            drift = target_non_long_total - current_non_long_total
            if abs(drift) > 0.1:
                # Distribute drift to the longest day (last in sorted list)
                last_idx = len(day_position_map) - 1
                last_day, last_dist, last_pos = day_position_map[last_idx]
                new_last_dist = max(MIN_EASY_MILES + MIN_PROGRESSION, last_dist + drift)
                # If we had to cap, distribute the remainder to other days
                actual_change = new_last_dist - last_dist
                remaining_drift = drift - actual_change

                day_position_map[last_idx] = (last_day, new_last_dist, last_pos)

                # If there's remaining drift, distribute to other days
                if abs(remaining_drift) > 0.1:
                    # Distribute to second-longest day (second-to-last)
                    if len(day_position_map) > 1:
                        second_last_idx = len(day_position_map) - 2
                        second_last_day, second_last_dist, second_last_pos = (
                            day_position_map[second_last_idx]
                        )
                        new_second_last_dist = max(
                            MIN_EASY_MILES, second_last_dist + remaining_drift
                        )
                        day_position_map[second_last_idx] = (
                            second_last_day,
                            new_second_last_dist,
                            second_last_pos,
                        )

        # Final pass: Re-enforce progression Mon < Wed < Thu with at least 1.0 mile increases
        for i in range(1, len(day_position_map)):
            prev_day, prev_dist, prev_pos = day_position_map[i - 1]
            curr_day, curr_dist, curr_pos = day_position_map[i]
            min_curr_dist = prev_dist + 1.0
            if curr_dist < min_curr_dist:
                day_position_map[i] = (curr_day, min_curr_dist, curr_pos)

        # Final verification: ensure total still matches (may need final adjustment)
        final_non_long_total = sum(dist for _, dist, _ in day_position_map)
        final_drift = target_non_long_total - final_non_long_total

        # If there's drift, adjust to maintain total
        # Priority: Hit target_total, then maintain progression where possible
        if abs(final_drift) > 0.1:
            if final_drift < 0:
                # Need to reduce: distribute reduction from longest to shortest (Thu → Wed → Mon)
                # This ensures we can reduce enough while maintaining progression
                remaining_reduction = -final_drift
                for i in range(
                    len(day_position_map) - 1, -1, -1
                ):  # Start from Thu (last)
                    if remaining_reduction <= 0.1:
                        break
                    day, dist, pos = day_position_map[i]
                    # Can reduce this day by up to (dist - MIN_EASY_MILES), but keep progression
                    min_dist = MIN_EASY_MILES
                    if i > 0:
                        # Must be at least prev_dist + 1.0
                        prev_day, prev_dist, prev_pos = day_position_map[i - 1]
                        min_dist = max(MIN_EASY_MILES, prev_dist + 1.0)

                    max_reduction = dist - min_dist
                    reduction = min(remaining_reduction, max_reduction)
                    new_dist = dist - reduction
                    remaining_reduction -= reduction
                    day_position_map[i] = (day, new_dist, pos)
            else:
                # Need to add: add to longest day (Thu)
                last_idx = len(day_position_map) - 1
                last_day, last_dist, last_pos = day_position_map[last_idx]
                new_last_dist = last_dist + final_drift
                if last_idx > 0:
                    _, prev_dist, _ = day_position_map[last_idx - 1]
                    new_last_dist = max(prev_dist + 1.0, new_last_dist)
                day_position_map[last_idx] = (last_day, new_last_dist, last_pos)

    # Step 6c: Build workouts list with recovery-aware ordering
    workouts: List[Dict[str, Any]] = []

    # Get run types - previous ordering: Easy → Medium → Easy/Tempo (longest weekday)
    run_type_priority = {"Easy": 0, "Medium": 1, "Easy/Tempo": 2, "Tempo": 3}
    sorted_run_types = sorted(run_types, key=lambda rt: run_type_priority.get(rt, 99))

    # Ensure Medium follows Easy
    if "Easy" in sorted_run_types and "Medium" in sorted_run_types:
        remaining_types = [
            rt for rt in sorted_run_types if rt not in ("Easy", "Medium")
        ]
        sorted_run_types = ["Easy", "Medium"] + remaining_types

    for i, (day, dist, forward_pos) in enumerate(day_position_map):
        run_type_idx = i if i < len(sorted_run_types) else len(sorted_run_types) - 1
        run_type = (
            sorted_run_types[run_type_idx]
            if run_type_idx < len(sorted_run_types)
            else "Easy"
        )
        distance = float(dist)

        # Map run type to previous labels
        workout_type_map = {
            "Medium": "Medium Run",
            "Easy": "Easy Run",
            "Easy/Tempo": "Easy/Tempo Run",
            "Tempo": "Tempo Run",
        }
        workout_type = workout_type_map.get(run_type, "Easy Run")

        workouts.append(
            {
                "day": day,
                "workout_type": workout_type,
                "distance_miles": distance,
                "pace_guidance": (
                    "Easy"
                    if "Easy" in run_type
                    else "Medium" if run_type == "Medium" else "Tempo"
                ),
                "workout_description": _get_workout_description(run_type),
            }
        )

    # Add long run workout
    workouts.append(
        {
            "day": long_day,
            "workout_type": "Long Run",
            "distance_miles": round_to_whole(long_run_miles),
            "pace_guidance": "Easy",
            "workout_description": "Steady easy long run",
        }
    )

    return workouts


def _get_workout_description(run_type: str) -> str:
    """Get workout description based on run type."""
    descriptions = {
        "Medium": "Moderate aerobic run for endurance building",
        "Easy": "Easy aerobic run for recovery and base building",
        "Easy/Tempo": "Easy run with optional tempo segments if feeling strong",
        "Tempo": "Tempo run at comfortably hard pace for speed development",
    }
    return descriptions.get(run_type, "Easy aerobic run")


class Pass3WorkoutDistribution:
    """Pass 3 - Deterministically distribute remaining mileage across non-long-run days."""

    def __init__(self):
        """Initialize Pass 3 workout distribution calculator."""
        pass

    def run(
        self, skel_long: List[Dict[str, Any]], training_days: List[str]
    ) -> Dict[str, Any]:
        """Calculate remaining days' workouts based on long run, total miles, and runs per week.

        This method uses a deterministic approach to distribute remaining mileage
        across non-long-run days using run-type percentages. It does NOT modify
        the long_run_miles or weekly_mileage values.

        Args:
            skel_long: List of weeks with week_number, phase, long_run_miles, weekly_mileage
            training_days: List of training days (e.g., ["Mon", "Wed", "Thu", "Sat"])

        Returns:
            Dict with "weeks" list containing workout distributions
        """
        if not training_days:
            training_days = ["Mon", "Wed", "Thu", "Sat"]

        runs_per_week = len(training_days)

        if runs_per_week not in (3, 4, 5):
            logger.warning(
                f"runs_per_week={runs_per_week} not in (3,4,5), defaulting to 4"
            )
            runs_per_week = 4

        weeks_out: List[Dict[str, Any]] = []

        for w in skel_long:
            week_num = int(w.get("week_number", len(weeks_out) + 1))
            long_run = float(w.get("long_run_miles", 0) or 0)
            weekly_total = float(w.get("weekly_mileage", 0) or 0)

            # Calculate workout distribution
            workouts = calculate_workout_distribution(
                long_run_miles=long_run,
                total_weekly_miles=weekly_total,
                runs_per_week=runs_per_week,
                training_days=training_days,
            )

            # Verify total matches (sanity check)
            workout_sum = sum(wk.get("distance_miles", 0) for wk in workouts)
            if abs(workout_sum - weekly_total) > 0.1:
                logger.warning(
                    f"Week {week_num}: Workout sum {workout_sum} ≠ weekly_total {weekly_total}"
                )

            weeks_out.append(
                {
                    "week_number": week_num,
                    "phase": w.get("phase", "Build"),
                    "weekly_mileage": weekly_total,  # Preserved exactly
                    "long_run_miles": long_run,  # Preserved exactly
                    "workouts": workouts,
                }
            )

        logger.info(f"Pass3 generated {len(weeks_out)} weeks of workout distributions")
        return {"weeks": weeks_out}
