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

    # Assign distances with swapped Wed/Thu:
    # Mon: shortest (Easy/Recovery - recovery after Saturday's LR)
    # Wed: longest weekday (Endurance - comes after Easy, builds endurance)
    # Thu: medium (Aerobic - comes before rest day Friday, not right before Long Run Saturday)
    # Pattern: Mon < Thu < Wed (by distance)
    # This ensures longer miles come after Easy day, and don't come right before Long Run
    if len(sorted_distances) >= 3:
        # 3+ days: Mon (shortest), Wed (longest), Thu (medium)
        for i, (day, _, forward_pos) in enumerate(day_position_map):
            if i == 0:
                # Mon: shortest
                day_position_map[i] = (day, sorted_distances[0], forward_pos)
            elif i == 1:
                # Wed: longest weekday (Endurance)
                day_position_map[i] = (day, sorted_distances[2], forward_pos)
            else:
                # Thu: medium (Aerobic)
                day_position_map[i] = (day, sorted_distances[1], forward_pos)
    elif len(sorted_distances) == 2:
        # 2 days: Mon (shortest) and one other (longest available)
        for i, (day, _, forward_pos) in enumerate(day_position_map):
            day_position_map[i] = (day, sorted_distances[i], forward_pos)
    else:
        # 1 day: shortest
        if day_position_map:
            day_position_map[0] = (
                day_position_map[0][0],
                sorted_distances[0],
                day_position_map[0][2],
            )

    # Single order-aware reconciliation
    if len(day_position_map) >= 3:
        # Extract Mon, Wed, Thu entries
        mon_idx = next(
            (i for i, (d, _, _) in enumerate(day_position_map) if d == "Mon"), None
        )
        wed_idx = next(
            (i for i, (d, _, _) in enumerate(day_position_map) if d == "Wed"), None
        )
        thu_idx = next(
            (i for i, (d, _, _) in enumerate(day_position_map) if d == "Thu"), None
        )

        if mon_idx is not None and wed_idx is not None and thu_idx is not None:
            mon_day, mon_dist, mon_pos = day_position_map[mon_idx]
            wed_day, wed_dist, wed_pos = day_position_map[wed_idx]
            thu_day, thu_dist, thu_pos = day_position_map[thu_idx]

            # Enforce minimums immediately on Mon/Thu; take from Wed if necessary
            if mon_dist < MIN_EASY_MILES:
                delta = MIN_EASY_MILES - mon_dist
                mon_dist = MIN_EASY_MILES
                wed_dist = max(MIN_EASY_MILES, wed_dist - delta)
            if thu_dist < MIN_EASY_MILES:
                delta = MIN_EASY_MILES - thu_dist
                thu_dist = MIN_EASY_MILES
                wed_dist = max(MIN_EASY_MILES, wed_dist - delta)

            # Enforce Mon < Thu < Wed (order-aware)
            if thu_dist <= mon_dist:
                needed = (mon_dist + 1.0) - thu_dist
                thu_dist += needed
                wed_dist = max(wed_dist - needed, MIN_EASY_MILES)
            if wed_dist <= thu_dist:
                needed = (thu_dist + 1.0) - wed_dist
                wed_dist += needed

            # Match non-long-run total exactly
            current_sum = mon_dist + thu_dist + wed_dist
            target_sum = non_long_total
            drift = round(current_sum - target_sum, 6)

            if abs(drift) > 0.1:
                if drift > 0:
                    # Need to reduce: Wed → Thu → Mon
                    reduce_order = [
                        (wed_idx, "Wed"),
                        (thu_idx, "Thu"),
                        (mon_idx, "Mon"),
                    ]
                    for idx, name in reduce_order:
                        if abs(drift) <= 0.1:
                            break
                        d_day, d_val, d_pos = day_position_map[idx]
                        min_allowed = MIN_EASY_MILES
                        if name == "Thu":
                            # Thu must remain > Mon by 1.0
                            min_allowed = max(min_allowed, mon_dist + 1.0)
                        if name == "Wed":
                            # Wed must remain > Thu by 1.0
                            min_allowed = max(min_allowed, thu_dist + 1.0)
                        can_reduce = max(0.0, d_val - min_allowed)
                        take = min(can_reduce, drift)
                        d_val -= take
                        drift -= take
                        if name == "Mon":
                            mon_dist = d_val
                        elif name == "Thu":
                            thu_dist = d_val
                        else:
                            wed_dist = d_val
                        day_position_map[idx] = (d_day, d_val, d_pos)
                else:
                    # Need to add: Thu → Wed → Mon
                    add = -drift
                    add_order = [(thu_idx, "Thu"), (wed_idx, "Wed"), (mon_idx, "Mon")]
                    for idx, name in add_order:
                        if add <= 0.1:
                            break
                        d_day, d_val, d_pos = day_position_map[idx]
                        # Respect ordering during addition
                        if name == "Thu":
                            min_needed = mon_dist + 1.0
                            d_val = max(d_val, min_needed)
                        if name == "Wed":
                            min_needed = thu_dist + 1.0
                            d_val = max(d_val, min_needed)
                        give = add
                        d_val += give
                        add -= give
                        if name == "Mon":
                            mon_dist = d_val
                        elif name == "Thu":
                            thu_dist = d_val
                        else:
                            wed_dist = d_val
                        day_position_map[idx] = (d_day, d_val, d_pos)

            # Write back reconciled values
            day_position_map[mon_idx] = (mon_day, mon_dist, mon_pos)
            day_position_map[thu_idx] = (thu_day, thu_dist, thu_pos)
            day_position_map[wed_idx] = (wed_day, wed_dist, wed_pos)

    # Final reconciliation to ensure weekday sum exactly matches target non-long-run total
    final_non_long_total = sum(dist for _, dist, _ in day_position_map)
    residual = round(non_long_total - final_non_long_total, 6)

    if abs(residual) > 0.1 and len(day_position_map) >= 3:
        # Identify Mon, Thu, Wed indices again
        mon_idx = next(
            (i for i, (d, _, _) in enumerate(day_position_map) if d == "Mon"), None
        )
        wed_idx = next(
            (i for i, (d, _, _) in enumerate(day_position_map) if d == "Wed"), None
        )
        thu_idx = next(
            (i for i, (d, _, _) in enumerate(day_position_map) if d == "Thu"), None
        )

        if mon_idx is not None and wed_idx is not None and thu_idx is not None:
            mon_day, mon_dist, mon_pos = day_position_map[mon_idx]
            wed_day, wed_dist, wed_pos = day_position_map[wed_idx]
            thu_day, thu_dist, thu_pos = day_position_map[thu_idx]

            if residual > 0:
                # Need to add miles: prefer Wed → Thu → Mon while preserving order
                add = residual
                # Add to Wed first
                give = add
                wed_dist += give
                add -= give
                # If still remaining (unlikely), add to Thu maintaining Thu >= Mon + 1
                if add > 0.1:
                    min_thu = max(MIN_EASY_MILES, mon_dist + 1.0)
                    if thu_dist < min_thu:
                        need = min_thu - thu_dist
                        take = min(add, need)
                        thu_dist += take
                        add -= take
                    if add > 0.1:
                        thu_dist += add
                        add = 0.0
            else:
                # Need to reduce miles: prefer Wed → Thu → Mon while preserving order
                take = -residual
                # Reduce from Wed first (keep > Thu + 1 and >= MIN)
                min_wed = max(MIN_EASY_MILES, thu_dist + 1.0)
                can = max(0.0, wed_dist - min_wed)
                used = min(can, take)
                wed_dist -= used
                take -= used
                # Then reduce from Thu (keep > Mon + 1 and >= MIN)
                if take > 0.1:
                    min_thu = max(MIN_EASY_MILES, mon_dist + 1.0)
                    can = max(0.0, thu_dist - min_thu)
                    used = min(can, take)
                    thu_dist -= used
                    take -= used
                # Finally reduce from Mon (keep >= MIN)
                if take > 0.1:
                    min_mon = MIN_EASY_MILES
                    can = max(0.0, mon_dist - min_mon)
                    used = min(can, take)
                    mon_dist -= used
                    take -= used

            # Write back
            day_position_map[mon_idx] = (mon_day, mon_dist, mon_pos)
            day_position_map[thu_idx] = (thu_day, thu_dist, thu_pos)
            day_position_map[wed_idx] = (wed_day, wed_dist, wed_pos)

    # Assert final equality (dev safety)
    final_non_long_total = sum(dist for _, dist, _ in day_position_map)
    if abs(final_non_long_total - non_long_total) > 0.1:
        raise ValueError(
            f"Weekday allocation drift: got {final_non_long_total}, expected {non_long_total}"
        )

        # Final pass: Re-enforce progression Mon < Thu < Wed (by distance)
        # Ensure: Mon (shortest) < Thu (medium) < Wed (longest weekday)
        # Find Mon, Wed, Thu by day name to enforce correct progression
        if len(day_position_map) >= 3:
            mon_entry = next(
                (
                    (i, entry)
                    for i, entry in enumerate(day_position_map)
                    if entry[0] == "Mon"
                ),
                None,
            )
            wed_entry = next(
                (
                    (i, entry)
                    for i, entry in enumerate(day_position_map)
                    if entry[0] == "Wed"
                ),
                None,
            )
            thu_entry = next(
                (
                    (i, entry)
                    for i, entry in enumerate(day_position_map)
                    if entry[0] == "Thu"
                ),
                None,
            )

            if mon_entry and wed_entry and thu_entry:
                mon_idx, (mon_day, mon_dist, mon_pos) = mon_entry
                wed_idx, (wed_day, wed_dist, wed_pos) = wed_entry
                thu_idx, (thu_day, thu_dist, thu_pos) = thu_entry

                # Ensure: Mon < Thu < Wed (by distance)
                if thu_dist <= mon_dist:
                    thu_dist = mon_dist + 1.0
                if wed_dist <= thu_dist:
                    wed_dist = thu_dist + 1.0

                day_position_map[mon_idx] = (mon_day, mon_dist, mon_pos)
                day_position_map[wed_idx] = (wed_day, wed_dist, wed_pos)
                day_position_map[thu_idx] = (thu_day, thu_dist, thu_pos)
        else:
            # Fallback: enforce sequential progression
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
                # Need to reduce: distribute reduction from longest to shortest (Wed → Thu → Mon)
                # Wed is longest weekday, so reduce from it first
                remaining_reduction = -final_drift
                # Find Wed (longest), then Thu, then Mon
                wed_idx = next(
                    (i for i, (d, _, _) in enumerate(day_position_map) if d == "Wed"),
                    len(day_position_map) - 1,
                )
                thu_idx = next(
                    (i for i, (d, _, _) in enumerate(day_position_map) if d == "Thu"),
                    len(day_position_map) - 2,
                )
                reduction_order = [wed_idx, thu_idx, 0]  # Wed (longest) → Thu → Mon
                for i in reduction_order:
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

    # Assign run types based on day and swapped Wed/Thu:
    # Mon: Easy → Easy/Recovery (shortest, recovery after Saturday's LR)
    # Wed: Easy/Tempo → Endurance (longest weekday, comes after Easy, builds endurance)
    # Thu: Medium → Aerobic (medium, comes before rest day Friday, not right before Long Run Saturday)

    for i, (day, dist, forward_pos) in enumerate(day_position_map):
        # Assign run type based on day name (not index)
        if day == "Mon":
            # Monday: Easy/Recovery (shortest, recovery day)
            run_type = "Easy"
        elif day == "Wed":
            # Wednesday: Endurance (longest weekday)
            run_type = (
                "Easy/Tempo"
                if "Easy/Tempo" in run_types
                else (run_types[2] if len(run_types) > 2 else "Easy")
            )
        elif day == "Thu":
            # Thursday: Aerobic (medium, before rest day)
            run_type = (
                "Medium"
                if "Medium" in run_types
                else (run_types[1] if len(run_types) > 1 else "Easy")
            )
        else:
            # Fallback for other days
            run_type_idx = i if i < len(run_types) else len(run_types) - 1
            run_type = (
                run_types[run_type_idx] if run_type_idx < len(run_types) else "Easy"
            )

        distance = float(dist)

        # Map run type to labels with new names
        workout_type_map = {
            "Medium": "Aerobic",
            "Easy": "Easy / Recovery",
            "Easy/Tempo": "Endurance",
            "Tempo": "Tempo",
        }
        workout_type = workout_type_map.get(run_type, "Easy / Recovery")

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
