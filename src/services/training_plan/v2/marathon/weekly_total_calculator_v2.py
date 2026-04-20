"""
Marathon Finisher Weekly Mileage Calculator V2

Given:
  - long_run (miles) for the week
  - runs_per_week (3, 4, 5, or 6)
  - prev_week_total (optional, for safe ramping)
  - config: RaceDistanceConfig (provides race-distance-specific values)

Returns a safe total weekly mileage target that minimizes injury risk
for a finisher-focused plan.

V2: Uses RaceDistanceConfig instead of hardcoded values.
"""

import logging
from typing import Any, Dict, List, Optional
from ..race_configs.base_config import RaceDistanceConfig
from ..shared_v2.rounding_utils import round_to_whole_mile

logger = logging.getLogger(__name__)


def clamp(n: float, lo: float, hi: float) -> float:
    """Clamp n between lo and hi."""
    return max(lo, min(hi, n))


def recommend_weekly_total(
    long_run: float,
    runs_per_week: int,
    config: RaceDistanceConfig,
    prev_week_total: Optional[float] = None,
    prev_prev_week_total: Optional[float] = None,
    rebuild_after_cutback: bool = False,
    peak_caps: Optional[Dict[int, int]] = None,
    starting_mileage_adjustment: float = 1.0,
    phase: Optional[str] = None,
    unit_system: str = "imperial",  # Deprecated: kept for backward compatibility, no longer affects rounding
) -> int:
    """Compute a safe weekly total given the long run and frequency.

    Args:
        long_run: Long run distance in miles
        runs_per_week: Number of runs per week (3, 4, 5, or 6)
        config: RaceDistanceConfig providing race-distance-specific values
        prev_week_total: Previous week's total (for safe ramping)
        prev_prev_week_total: Week before previous (for post-cutback rebuild)
        rebuild_after_cutback: Whether this is a rebuild week after cutback
        peak_caps: Custom peak caps (defaults to config.peak_caps)
        starting_mileage_adjustment: Adjustment factor for Week 1 (default 1.0 = no adjustment)
        phase: Training phase label for the week (e.g., Base, Build, Peak, Taper)
        unit_system: Deprecated - kept for backward compatibility. Weekly totals are always
                     rounded to whole miles internally. Frontend handles unit conversion for display.

    Returns:
        Safe weekly total in whole miles (always rounded to whole miles, regardless of unit_system)
    """
    if runs_per_week not in (3, 4, 5, 6):
        raise ValueError("runs_per_week must be 3, 4, 5, or 6")

    # Get values from config
    lo_pct, hi_pct = config.long_run_percentage_ranges[runs_per_week]
    # Calculate target as midpoint
    target_pct = (lo_pct + hi_pct) / 2.0

    # Base target from long-run percentage
    base_total = long_run / target_pct

    # Respect range derived from pct bounds
    min_total = long_run / hi_pct  # higher pct → lower total
    max_total = long_run / lo_pct  # lower pct → higher total

    total = clamp(base_total, min_total, max_total)

    # Apply previous-week ramp cap if provided, BUT ensure LR % requirement is met
    if rebuild_after_cutback and prev_prev_week_total and prev_prev_week_total > 0:
        baseline = prev_prev_week_total
        weekly_increase_cap = config.weekly_increase_cap
        rebound_cap = min(
            baseline + 4.0,  # add at most ~4 miles
            baseline * (1 + weekly_increase_cap * 2),  # roughly 15-16%
        )
        total = min(total, rebound_cap)
    elif prev_week_total is not None and prev_week_total > 0:
        weekly_increase_cap = config.weekly_increase_cap
        capped_total = prev_week_total * (1 + weekly_increase_cap)
        total = min(total, capped_total)

    # Ensure minimum viability after ramp calculations
    min_non_long_day = config.min_non_long_day
    min_total_viable = long_run + (runs_per_week - 1) * min_non_long_day
    total = max(total, min_total_viable)

    # Apply finisher peak cap
    caps = peak_caps or config.peak_caps
    total = min(total, caps[runs_per_week])

    # Apply starting mileage adjustment (only for Week 1, when prev_week_total is None)
    if prev_week_total is None and starting_mileage_adjustment != 1.0:
        total = total * starting_mileage_adjustment
        # Ensure adjusted total still meets minimum
        min_non_long_day = config.min_non_long_day
        min_total_viable = long_run + (runs_per_week - 1) * min_non_long_day
        total = max(total, min_total_viable)

    # Apply phase-specific week-over-week caps (if configured)
    phase_caps = getattr(config, "phase_delta_caps", None)
    if phase_caps and phase and prev_week_total is not None and prev_week_total > 0:
        normalized_phase = phase.lower()
        delta_cap = None
        for key, value in phase_caps.items():
            if key.lower() == normalized_phase:
                delta_cap = value
                break

        if delta_cap is not None:
            allowed_total = prev_week_total * (1 + delta_cap)
            capped_total = min(total, allowed_total)
            if capped_total < total - 0.05:
                logger.debug(
                    "Phase cap applied: %s week limited from %.1f → %.1f (delta cap %.1f%%)",
                    phase,
                    total,
                    capped_total,
                    delta_cap * 100,
                )
            total = capped_total

    # CRITICAL: Always round to whole miles for internal consistency
    # Frontend will convert to km for display using toDisplayDistance()
    # This prevents metric plans from diverging due to rounding differences
    return round_to_whole_mile(total)


def calculate_weekly_totals_from_long_runs(
    weeks: List[Dict[str, Any]],
    runs_per_week: int,
    config: RaceDistanceConfig,
    peak_caps: Optional[Dict[int, int]] = None,
    scenario_adjustments: Optional[Dict[str, Any]] = None,
    unit_system: str = "imperial",
) -> List[Dict[str, Any]]:
    """Calculate weekly totals for all weeks based on long runs.

    Args:
        weeks: List of week dicts with 'week_number' and 'long_run_miles'
        runs_per_week: Number of runs per week (3, 4, 5, or 6)
        config: RaceDistanceConfig providing race-distance-specific values
        peak_caps: Custom peak caps (optional, defaults to config.peak_caps)
        scenario_adjustments: Optional scenario-specific adjustments dict

    Returns:
        Updated weeks list with 'weekly_mileage' added
    """
    result = []
    prev_total: Optional[float] = None
    prev_prev_total: Optional[float] = None
    rebuild_next_week = False
    starting_mileage_adjustment = (
        scenario_adjustments.get("starting_mileage_adjustment", 1.0)
        if scenario_adjustments
        else 1.0
    )

    for week in weeks:
        week_num = week.get("week_number", 0)
        long_run = float(week.get("long_run_miles", 0) or 0)
        phase = week.get("phase")

        if long_run > 0:
            total = recommend_weekly_total(
                long_run=long_run,
                runs_per_week=runs_per_week,
                config=config,
                prev_week_total=prev_total,
                prev_prev_week_total=prev_prev_total,
                rebuild_after_cutback=rebuild_next_week,
                peak_caps=peak_caps,
                starting_mileage_adjustment=(
                    starting_mileage_adjustment if week_num == 1 else 1.0
                ),
                phase=phase,
                unit_system=unit_system,
            )
            prev_prev_total = prev_total
            prev_total = float(total)
        else:
            total = 0
            prev_prev_total = prev_total
            prev_total = None

        # Keep rebuild cadence aligned with the long-run spine.
        # Prefer explicit spine metadata over inferred mileage drops.
        if "is_cutback" in week:
            rebuild_next_week = bool(week.get("is_cutback"))
        elif prev_prev_total is not None and prev_total is not None:
            # Backward-compatible fallback for callers that don't pass `is_cutback`.
            rebuild_next_week = (
                prev_prev_total > 0 and prev_total <= prev_prev_total * 0.8
            )
        else:
            rebuild_next_week = False

        # Create updated week dict (preserve existing fields, add weekly_mileage)
        updated_week = dict(week)
        updated_week["weekly_mileage"] = total
        result.append(updated_week)

    return result
