"""
Pass 3: Workout Distribution Service

Purpose:
    Distribute remaining weekly mileage across non-long-run days using
    forward-distance-based assignment from the long run. This is a deterministic
    calculation that does NOT modify long_run_miles or weekly_mileage values.

Responsibilities:
    - Take long_run_miles, total_weekly_miles, and training_days as inputs
    - Calculate non-long-run total mileage
    - Distribute remaining mileage using Hamilton apportionment (unbiased rounding)
    - Assign workout types by forward distance from long run (circular)
    - Ensure minimum 3 miles per non-long run
    - Handle rounding to match total_weekly_miles exactly

Design:
    - Deterministic (no LLM calls)
    - Preserves long_run_miles and weekly_mileage (read-only)
    - Uses forward-distance invariants (closest=EASY, farthest=ENDURANCE, middle=STEADY)
    - Works for any run_days order and any long_run day placement

Invariants:
    I1. Closest non-long day to LONG → EASY (smallest non-long mileage)
    I2. Farthest non-long day → ENDURANCE (largest non-long mileage)
    I3. Remaining day(s) → STEADY; within STEADY, farther gets more
    I4. Never reduce the long run to satisfy minimums
    I5. Works for any run_days order and any long_idx (3/4/5 runs)

Usage:
    Used by orchestrator_three_pass.py to assign workout roles and distances
    based on forward-distance from the long run day.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from math import floor
from typing import Any, Dict, List
import logging

from src.services.training_plan.workout_types import (
    EASY,
    STEADY,
    ENDURANCE,
    LONG,
    TYPE_DISPLAY,
    TYPE_DESCRIPTIONS,
    NON_LONG_SHARES,
    SLOT_COUNTS,
    MIN_NON_LONG_DAY,
    PACE_GUIDANCE,
)

logger = logging.getLogger(__name__)


def _largest_remainder(total: float, shares: List[float]) -> List[int]:
    """Hamilton apportionment: unbiased rounding.

    This method ensures that the sum of rounded allocations exactly equals
    the total, while minimizing rounding bias by assigning remainder to
    slots with the largest fractional parts.

    Args:
        total: Total amount to distribute
        shares: List of share percentages (must sum to 1.0)

    Returns:
        List of allocated amounts (as integers) that sum to total
    """
    if total == 0:
        return [0] * len(shares)

    raw = [total * s for s in shares]
    floors = [floor(x) for x in raw]
    remainder = int(round(total)) - sum(floors)

    if remainder == 0:
        return floors

    # Assign remaining 1's to largest fractional parts
    idxs = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in idxs[:remainder]:
        floors[i] += 1

    return floors  # Sums to total (or total rounded)


def calculate_workout_distribution(
    weekly_total: float,
    long_run_miles: float,
    run_days: List[str],
    long_idx: int = None,
) -> Dict[str, Dict[str, Any]]:
    """Calculate workout distribution for a single week.

    This function uses forward-distance-based assignment: the closest day to
    the long run gets EASY (shortest), the farthest gets ENDURANCE (longest),
    and middle days get STEADY.

    Args:
        weekly_total: Total weekly mileage (fixed, not modified)
        long_run_miles: Long run distance (fixed, not modified)
        run_days: Ordered list of training days (e.g., ["Mon", "Wed", "Thu", "Sat"])
        long_idx: Index of long run day in run_days; default = last day

    Returns:
        Dict mapping day_name -> {
            "type": str (EASY/STEADY/ENDURANCE/LONG),
            "label": str (display name),
            "miles": int (distance in miles)
        }
    """
    n = len(run_days)
    assert n in (3, 4, 5), f"runs_per_week must be 3, 4, or 5, got {n}"

    if long_idx is None:
        long_idx = n - 1  # Default to last day
    assert 0 <= long_idx < n, f"long_idx {long_idx} out of range for {n} days"

    # Validate shares sum to 1.0
    shares = NON_LONG_SHARES[n]
    assert (
        abs(sum(shares) - 1.0) < 0.001
    ), f"Shares for {n}-day plan must sum to 1.0, got {sum(shares)}"

    # 1) Calculate circular forward distance from LONG to each day
    fwd = [(i - long_idx) % n for i in range(n)]

    # 2) Identify non-long day indices sorted by forward distance (closest..farthest)
    non_long_idxs = [i for i in range(n) if i != long_idx]
    non_long_idxs.sort(key=lambda i: fwd[i])

    # Validate share/slot count match
    assert len(shares) == len(
        non_long_idxs
    ), f"Share count {len(shares)} != non-long slot count {len(non_long_idxs)}"

    # 3) Compute non-long miles via unbiased apportionment
    non_long_total = max(0.0, weekly_total - long_run_miles)
    # Distances longest→...→shortest (matching shares order)
    parts_desc = _largest_remainder(non_long_total, shares)

    # 4) Role assignment with safety guard for day-before-long run
    roles = {run_days[long_idx]: LONG}  # Long day

    # Identify the slot immediately before the long run (calendar order)
    prev_idx = (long_idx - 1) % n
    day_before_is_run = prev_idx in non_long_idxs

    # Determine safe ENDURANCE candidate(s): prefer slots at least 2 days away
    def calendar_gap(idx: int) -> int:
        return (idx - long_idx) % n

    safe_endurance_candidates = [
        idx for idx in non_long_idxs if idx != prev_idx and calendar_gap(idx) >= 2
    ]
    if not safe_endurance_candidates:
        # Fallback: use the farthest non-long slot (even if adjacent) to avoid failure
        safe_endurance_candidates = [i for i in non_long_idxs if i != prev_idx]
        if not safe_endurance_candidates:
            safe_endurance_candidates = non_long_idxs.copy()

    # Choose ENDURANCE slot with largest gap (furthest in calendar days)
    far_idx = max(safe_endurance_candidates, key=calendar_gap)
    roles[run_days[far_idx]] = ENDURANCE

    # Assign EASY slot:
    #  - If the day before the long run is a training day, force it to be EASY.
    #  - Otherwise, use the closest slot in forward distance ordering.
    if day_before_is_run:
        close_idx = prev_idx
    else:
        close_idx = non_long_idxs[0]

    roles[run_days[close_idx]] = EASY

    # Remainder → STEADY
    for i in non_long_idxs:
        if run_days[i] not in roles:
            roles[run_days[i]] = STEADY

    # 5) Assign miles to roles by size:
    #    ENDURANCE gets largest, EASY gets smallest, STEADY gets middles
    # Reorder the non-long mile buckets so that:
    #  - ENDURANCE gets the largest share
    #  - EASY gets the smallest
    #  - STEADY days get the middles (ascending with proximity)
    parts_desc_sorted = sorted(parts_desc)
    smallest = parts_desc_sorted[0]
    largest = parts_desc_sorted[-1]
    steadies = parts_desc_sorted[1:-1]  # May be empty

    # STEADY positions ordered by forward distance (closer first)
    steady_positions = [i for i in non_long_idxs if roles[run_days[i]] == STEADY]
    steady_positions.sort(key=lambda i: fwd[i])  # Closest steady gets smaller miles

    miles = {}
    # Start with long
    miles[run_days[long_idx]] = long_run_miles

    # ENDURANCE
    miles[run_days[far_idx]] = max(MIN_NON_LONG_DAY, largest)

    # EASY
    miles[run_days[close_idx]] = max(MIN_NON_LONG_DAY, smallest)

    # STEADY (distribute middles: closer gets smaller, farther gets larger)
    for amt, i in zip(sorted(steadies), steady_positions):
        miles[run_days[i]] = max(MIN_NON_LONG_DAY, amt)

    # 6) If mins pushed us over total, trim in priority order:
    #    ENDURANCE → farthest STEADY → closer STEADY
    #    Never trim from LONG (Invariant I4)
    over = sum(miles.values()) - weekly_total
    if over > 0:
        trim_order = [run_days[far_idx]] + steady_positions[::-1]
        for d in trim_order:
            if over <= 0:
                break
            reducible = max(0, miles[d] - MIN_NON_LONG_DAY)
            take = min(reducible, over)
            miles[d] -= take
            over -= take

        if over > 0:
            logger.warning(
                f"Could not fully trim overage: {over:.1f} miles remain "
                f"(weekly_total={weekly_total}, long_run={long_run_miles})"
            )

    # 7) Build schedule
    out = {}
    for day in run_days:
        role = roles[day]
        day_miles = miles.get(day, 0)
        out[day] = {
            "type": role,
            "label": TYPE_DISPLAY[role],
            "miles": int(day_miles),
            "workout_type": TYPE_DISPLAY[role],  # For backward compatibility
            "distance_miles": float(day_miles),  # For backward compatibility
            "pace_guidance": PACE_GUIDANCE[role],
            "workout_description": TYPE_DESCRIPTIONS[role],
            "day": day,  # For backward compatibility
        }
    return out


def validate_workout_distribution(
    schedule: Dict[str, Dict[str, Any]],
    run_days: List[str],
    long_idx: int,
    weekly_total: float,
    long_run_miles: float,
    freq: int,
) -> tuple[List[str], List[str]]:
    """Validate Invariants I1-I5 and checks V1-V6.

    Args:
        schedule: Output from calculate_workout_distribution
        run_days: Ordered list of training days
        long_idx: Index of long run day
        weekly_total: Expected total weekly mileage
        long_run_miles: Expected long run mileage
        freq: Number of runs per week (3, 4, or 5)

    Returns:
        Tuple of (errors, warnings) - lists of validation messages
    """
    errors = []
    warnings = []

    n = len(run_days)
    fwd = [(i - long_idx) % n for i in range(n)]

    # V1: Sum equals weekly_total; long equals long_run_miles
    total_miles = sum(schedule[day]["miles"] for day in run_days)
    if abs(total_miles - weekly_total) > 0.1:
        errors.append(f"Total miles {total_miles} != weekly_total {weekly_total}")

    long_day = run_days[long_idx]
    if abs(schedule[long_day]["miles"] - long_run_miles) > 0.1:
        errors.append(f"Long run {schedule[long_day]['miles']} != {long_run_miles}")

    # Get non-long days sorted by forward distance
    non_long_idxs = [i for i in range(n) if i != long_idx]
    non_long_idxs.sort(key=lambda i: fwd[i])

    if not non_long_idxs:
        return errors, warnings

    closest_idx = non_long_idxs[0]
    farthest_idx = non_long_idxs[-1]
    closest_day = run_days[closest_idx]
    farthest_day = run_days[farthest_idx]

    # V2: Closest is EASY and has smallest non-long miles
    if schedule[closest_day]["type"] != EASY:
        errors.append(
            f"Closest day {closest_day} should be EASY, "
            f"got {schedule[closest_day]['type']}"
        )

    closest_miles = schedule[closest_day]["miles"]
    non_long_miles = [schedule[run_days[i]]["miles"] for i in non_long_idxs]
    if closest_miles != min(non_long_miles):
        errors.append(f"Closest day {closest_day} should have smallest non-long miles")

    # V3: Farthest is ENDURANCE and has largest non-long miles
    if schedule[farthest_day]["type"] != ENDURANCE:
        errors.append(
            f"Farthest day {farthest_day} should be ENDURANCE, "
            f"got {schedule[farthest_day]['type']}"
        )

    farthest_miles = schedule[farthest_day]["miles"]
    if farthest_miles != max(non_long_miles):
        errors.append(f"Farthest day {farthest_day} should have largest non-long miles")

    # V4: STEADY days ordered by forward distance have non-decreasing miles
    steady_idxs = [i for i in non_long_idxs if schedule[run_days[i]]["type"] == STEADY]
    steady_idxs.sort(key=lambda i: fwd[i])  # Closest→farthest
    for i in range(len(steady_idxs) - 1):
        curr_idx = steady_idxs[i]
        next_idx = steady_idxs[i + 1]
        curr_miles = schedule[run_days[curr_idx]]["miles"]
        next_miles = schedule[run_days[next_idx]]["miles"]
        if curr_miles > next_miles:
            errors.append(
                f"STEADY ordering violated: {run_days[curr_idx]}={curr_miles} "
                f"> {run_days[next_idx]}={next_miles}"
            )

    # V5: Each non-long ≥ MIN_NON_LONG_DAY
    for idx in non_long_idxs:
        day = run_days[idx]
        if schedule[day]["miles"] < MIN_NON_LONG_DAY:
            errors.append(
                f"Day {day} below minimum: {schedule[day]['miles']} "
                f"< {MIN_NON_LONG_DAY}"
            )

    # V6: Long-run share in expected range
    from src.services.training_plan.workout_types import LONG_RUN_SHARE_RANGES

    long_share = long_run_miles / weekly_total if weekly_total > 0 else 0
    expected_ranges = LONG_RUN_SHARE_RANGES
    if freq in expected_ranges:
        lo, hi = expected_ranges[freq]
        if not (lo <= long_share <= hi):
            warnings.append(
                f"Long-run share {long_share:.1%} outside expected range "
                f"[{lo:.1%}, {hi:.1%}] for {freq}-day plan"
            )

    return errors, warnings


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
        across non-long-run days using forward-distance-based assignment. It does NOT
        modify the long_run_miles or weekly_mileage values.

        Args:
            skel_long: List of weeks with week_number, phase, long_run_miles, weekly_mileage
            training_days: List of training days (e.g., ["Mon", "Wed", "Thu", "Sat"])

        Returns:
            Dict with "weeks" list containing workout distributions
        """
        from src.utils.date_helpers import DEFAULT_TRAINING_DAYS

        if not training_days:
            training_days = DEFAULT_TRAINING_DAYS

        runs_per_week = len(training_days)

        if runs_per_week not in (3, 4, 5):
            logger.warning(
                f"runs_per_week={runs_per_week} not in (3,4,5), defaulting to 4"
            )
            from src.utils.date_helpers import DEFAULT_TRAINING_DAYS

            runs_per_week = 4
            training_days = DEFAULT_TRAINING_DAYS

        weeks_out: List[Dict[str, Any]] = []

        for w in skel_long:
            week_num = int(w.get("week_number", len(weeks_out) + 1))
            long_run = float(w.get("long_run_miles", 0) or 0)
            weekly_total = float(w.get("weekly_mileage", 0) or 0)

            # Determine long run day (prefer Sat, then Sun, else last day)
            from src.utils.date_helpers import DAY_NAMES_ABBREV

            long_idx = None
            if DAY_NAMES_ABBREV[5] in training_days:  # Saturday
                long_idx = training_days.index(DAY_NAMES_ABBREV[5])
            elif DAY_NAMES_ABBREV[6] in training_days:  # Sunday
                long_idx = training_days.index(DAY_NAMES_ABBREV[6])
            else:
                long_idx = len(training_days) - 1  # Default to last day

            # Calculate workout distribution using new forward-distance method
            schedule = calculate_workout_distribution(
                weekly_total=weekly_total,
                long_run_miles=long_run,
                run_days=training_days,
                long_idx=long_idx,
            )

            # Convert schedule dict to list format (for backward compatibility)
            # Maintain order by training_days to ensure consistent ordering
            workouts = []
            for day in training_days:
                if day in schedule:
                    workout_data = schedule[day].copy()
                    # Ensure day field is set (used by plan_storage_service)
                    workout_data["day"] = day
                    workouts.append(workout_data)

            # Validate (optional, for debugging)
            errors, warnings = validate_workout_distribution(
                schedule=schedule,
                run_days=training_days,
                long_idx=long_idx,
                weekly_total=weekly_total,
                long_run_miles=long_run,
                freq=runs_per_week,
            )

            if errors:
                logger.error(f"Week {week_num} validation errors: {', '.join(errors)}")
            if warnings:
                logger.warning(
                    f"Week {week_num} validation warnings: {', '.join(warnings)}"
                )

            # Verify total matches (sanity check)
            workout_sum = sum(
                wk.get("distance_miles", wk.get("miles", 0)) for wk in workouts
            )
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
