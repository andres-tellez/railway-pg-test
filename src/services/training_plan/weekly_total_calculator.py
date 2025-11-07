"""
Marathon Finisher Weekly Mileage Calculator

Given:
  - long_run (miles) for the week
  - runs_per_week (3, 4, or 5)
  - prev_week_total (optional, for safe ramping)

Returns a safe total weekly mileage target that minimizes injury risk
for a finisher-focused plan.

Core ideas:
- For finishers, the long run should be a large share of weekly mileage.
- We model that share by runs per week:
    * 3 days/week:   long run ≈ 40–50% of weekly total (target 45%)
    * 4 days/week:   long run ≈ 35–45% (target 40%)
    * 5 days/week:   long run ≈ 30–40% (target 33%)
- Safety rules:
    * Weekly increase cap: +8% vs. previous week (if provided)
    * Absolute peak caps for finishers:
        - 3 days: 42 mi peak
        - 4 days: 46 mi peak
        - 5 days: 50 mi peak
    * Minimum viable mileage: ≥ 3 mi per non-long run
"""

from typing import Any, Dict, List, Optional

# Long run percentage targets (midpoint of ranges)
PCT_TARGET = {
    3: 0.45,  # mid of 40-50%
    4: 0.40,  # mid of 35-45%
    5: 0.33,  # mid of 30-40%
}

# Long run percentage ranges
PCT_RANGE = {
    3: (0.40, 0.50),
    4: (0.35, 0.45),
    5: (0.30, 0.40),
}

# Peak caps for finisher plans
PEAK_CAP_DEFAULT = {
    3: 42,
    4: 46,
    5: 50,
}

MIN_NON_LONG_DAY = 3  # miles
WEEKLY_INCREASE_CAP = 0.08  # +8%


def clamp(n: float, lo: float, hi: float) -> float:
    """Clamp n between lo and hi."""
    return max(lo, min(hi, n))


def recommend_weekly_total(
    long_run: float,
    runs_per_week: int,
    prev_week_total: Optional[float] = None,
    peak_caps: Optional[Dict[int, int]] = None,
) -> int:
    """Compute a safe weekly total given the long run and frequency.

    Args:
        long_run: Long run distance in miles
        runs_per_week: Number of runs per week (3, 4, or 5)
        prev_week_total: Previous week's total (for safe ramping)
        peak_caps: Custom peak caps (defaults to PEAK_CAP_DEFAULT)

    Returns:
        Safe weekly total in whole miles
    """
    if runs_per_week not in (3, 4, 5):
        raise ValueError("runs_per_week must be 3, 4, or 5")

    target_pct = PCT_TARGET[runs_per_week]
    lo_pct, hi_pct = PCT_RANGE[runs_per_week]

    # Base target from long-run percentage
    base_total = long_run / target_pct

    # Respect range derived from pct bounds
    min_total = long_run / hi_pct  # higher pct → lower total
    max_total = long_run / lo_pct  # lower pct → higher total

    total = clamp(base_total, min_total, max_total)

    # Ensure minimum viability: each non-long day ≥ 3 miles
    min_total_viable = long_run + (runs_per_week - 1) * MIN_NON_LONG_DAY
    total = max(total, min_total_viable)

    # Apply previous-week ramp cap if provided, BUT ensure LR % requirement is met
    if prev_week_total is not None and prev_week_total > 0:
        capped_total = prev_week_total * (1 + WEEKLY_INCREASE_CAP)
        # If cap would violate LR % range, use the minimum needed to meet LR % requirement
        if capped_total < min_total:
            # After cutback, allow larger increase to meet LR % requirement
            total = max(total, min_total)
        else:
            total = min(total, capped_total)

    # Apply finisher peak cap
    caps = peak_caps or PEAK_CAP_DEFAULT
    total = min(total, caps[runs_per_week])

    return int(round(total))


def calculate_weekly_totals_from_long_runs(
    weeks: List[Dict[str, Any]],
    runs_per_week: int,
    peak_caps: Optional[Dict[int, int]] = None,
) -> List[Dict[str, Any]]:
    """Calculate weekly totals for all weeks based on long runs.

    Args:
        weeks: List of week dicts with 'week_number' and 'long_run_miles'
        runs_per_week: Number of runs per week (3, 4, or 5)
        peak_caps: Custom peak caps (optional)

    Returns:
        Updated weeks list with 'weekly_mileage' added
    """
    result = []
    prev_total: Optional[float] = None

    for week in weeks:
        week_num = week.get("week_number", 0)
        long_run = float(week.get("long_run_miles", 0) or 0)

        if long_run > 0:
            total = recommend_weekly_total(
                long_run=long_run,
                runs_per_week=runs_per_week,
                prev_week_total=prev_total,
                peak_caps=peak_caps,
            )
            prev_total = float(total)
        else:
            total = 0
            prev_total = None

        # Create updated week dict (preserve existing fields, add weekly_mileage)
        updated_week = dict(week)
        updated_week["weekly_mileage"] = total
        result.append(updated_week)

    return result
