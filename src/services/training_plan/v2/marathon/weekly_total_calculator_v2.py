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

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from ..race_configs.base_config import RaceDistanceConfig
from ..shared_v2.rounding_utils import round_to_whole_mile

logger = logging.getLogger(__name__)


def _phase_is_peak(phase: Optional[str]) -> bool:
    if not phase:
        return False
    return str(phase).lower().strip() == "peak"


def _phase_is_taper(phase: Optional[str]) -> bool:
    if not phase:
        return False
    p = str(phase).lower().strip()
    return p in ("taper", "taper week")


def _phase_is_build(phase: Optional[str]) -> bool:
    if not phase:
        return False
    return str(phase).lower().strip() == "build"


def _first_taper_week_number(weeks: List[Dict[str, Any]]) -> Optional[int]:
    """Smallest ``week_number`` among weeks labeled Taper (calendar first taper week)."""
    best: Optional[int] = None
    for w in weeks:
        if not _phase_is_taper(w.get("phase")):
            continue
        try:
            n = int(w.get("week_number", 0) or 0)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        if best is None or n < best:
            best = n
    return best


def _should_apply_finisher_peak_weekly_cap(
    phase: Optional[str],
    weeks_before_first_taper: Optional[int],
    lookahead_weeks: int,
) -> bool:
    """Peak weekly cap applies in Peak and final pre-taper weeks, not Build or Taper."""
    if _phase_is_taper(phase):
        return False
    if _phase_is_build(phase):
        return False
    if _phase_is_peak(phase):
        return True
    if (
        weeks_before_first_taper is not None
        and 0 <= weeks_before_first_taper <= lookahead_weeks
    ):
        return True
    if phase is None or not str(phase).strip():
        return True
    return False


def clamp(n: float, lo: float, hi: float) -> float:
    """Clamp n between lo and hi."""
    return max(lo, min(hi, n))


def _weekly_total_largest_step(
    chain: List[Tuple[str, float]],
) -> Tuple[Optional[str], float]:
    """Largest |delta| between consecutive (name, value) chain points."""
    if len(chain) < 2:
        return (None, 0.0)
    prev_name, prev_val = chain[0]
    best_edge: Optional[str] = None
    best_abs = 0.0
    for name, val in chain[1:]:
        delta = val - prev_val
        ad = abs(delta)
        if ad > best_abs + 1e-9:
            best_abs = ad
            best_edge = f"{prev_name}->{name}"
        prev_name, prev_val = name, val
    return (best_edge, best_abs)


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
    prev_phase: Optional[str] = None,
    # Deprecated: backward compatibility only; does not affect rounding.
    unit_system: str = "imperial",
    week_number: Optional[int] = None,
    prev_long_run: Optional[float] = None,
    is_cutback: Optional[bool] = None,
    weeks_before_first_taper: Optional[int] = None,
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
        prev_phase: Prior week's phase; used with ``phase`` for Peak→Taper boundary capping
        unit_system: Deprecated. Weekly totals are whole miles internally.
        week_number: Optional week index for DEBUG tracing only.
        prev_long_run: Prior week's long run (miles); DEBUG trace context.
        is_cutback: Optional spine flag for DEBUG tracing only.
        weeks_before_first_taper: ``first_taper_week_number - week_number`` until taper.
            Gates finisher peak weekly cap with Peak phase; Build never uses this cap.

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

    after_lr_clamp = clamp(base_total, min_total, max_total)
    total = after_lr_clamp

    # Apply previous-week ramp cap if provided, BUT ensure LR % requirement is met
    after_volume_cap = after_lr_clamp
    volume_cap_kind = "none"
    if rebuild_after_cutback and prev_prev_week_total and prev_prev_week_total > 0:
        baseline = prev_prev_week_total
        weekly_increase_cap = config.weekly_increase_cap
        rebound_cap = min(
            baseline + 4.0,  # add at most ~4 miles
            baseline * (1 + weekly_increase_cap * 2),  # roughly 15-16%
        )
        total = min(total, rebound_cap)
        after_volume_cap = total
        volume_cap_kind = "rebuild_rebound"
    elif prev_week_total is not None and prev_week_total > 0:
        weekly_increase_cap = config.weekly_increase_cap
        capped_total = prev_week_total * (1 + weekly_increase_cap)
        total = min(total, capped_total)
        after_volume_cap = total
        volume_cap_kind = "prev_week_ramp"
    else:
        after_volume_cap = total

    # Ensure minimum viability after ramp calculations
    min_non_long_day = config.min_non_long_day
    min_total_viable = long_run + (runs_per_week - 1) * min_non_long_day
    total = max(total, min_total_viable)
    after_min_viable = total

    # Apply finisher peak cap (Peak / final pre-taper window only — not Build or Taper)
    caps = peak_caps or config.peak_caps
    lookahead = int(config.peak_weekly_cap_lookahead_weeks_before_taper)
    apply_peak_weekly_cap = _should_apply_finisher_peak_weekly_cap(
        phase, weeks_before_first_taper, lookahead
    )
    if apply_peak_weekly_cap:
        total = min(total, caps[runs_per_week])
    after_peak_cap = total

    # Apply starting mileage adjustment (only for Week 1, when prev_week_total is None)
    after_starting_adj = after_peak_cap
    after_min_viable_post_starting = after_peak_cap
    if prev_week_total is None and starting_mileage_adjustment != 1.0:
        total = total * starting_mileage_adjustment
        after_starting_adj = total
        # Ensure adjusted total still meets minimum
        min_non_long_day = config.min_non_long_day
        min_total_viable = long_run + (runs_per_week - 1) * min_non_long_day
        total = max(total, min_total_viable)
        after_min_viable_post_starting = total
    else:
        after_starting_adj = after_peak_cap
        after_min_viable_post_starting = total

    # Apply phase-specific week-over-week caps (if configured)
    after_phase_cap = after_min_viable_post_starting
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
            after_phase_cap = total

    # Peak → Taper: first taper week must not retain peak-level weekly load (boundary only).
    after_peak_taper = after_phase_cap
    if (
        _phase_is_taper(phase)
        and _phase_is_peak(prev_phase)
        and prev_week_total is not None
        and prev_week_total > 0
    ):
        max_ratio = float(
            getattr(
                config,
                "peak_to_taper_first_week_max_ratio",
                0.90,
            )
        )
        ceiling = prev_week_total * max_ratio
        if total > ceiling + 1e-6:
            logger.debug(
                "Peak→Taper boundary: capped weekly total from %.1f to %.1f "
                "(≤%.0f%% of final peak week %.1f)",
                total,
                ceiling,
                max_ratio * 100,
                prev_week_total,
            )
        total = min(total, ceiling)
        after_peak_taper = total

    before_round = total
    rounded = round_to_whole_mile(total)

    if logger.isEnabledFor(logging.DEBUG):
        chain: List[Tuple[str, float]] = [
            ("after_lr_clamp", after_lr_clamp),
            ("after_volume_cap", after_volume_cap),
            ("after_min_viable", after_min_viable),
            ("after_peak_cap", after_peak_cap),
            ("after_starting_adj", after_starting_adj),
            ("after_min_viable_post_starting", after_min_viable_post_starting),
            ("after_phase_cap", after_phase_cap),
            ("after_peak_taper", after_peak_taper),
            ("before_round", before_round),
        ]
        largest_edge, largest_abs = _weekly_total_largest_step(chain)
        lr_down = (
            prev_long_run is not None
            and prev_long_run > 0
            and long_run + 1e-6 < prev_long_run
        )
        total_up_despite_lr_down = (
            lr_down
            and prev_week_total is not None
            and before_round > prev_week_total + 0.25
        )
        trace = {
            "event": "weekly_total_trace",
            "week_number": week_number,
            "phase": phase,
            "prev_phase": prev_phase,
            "weeks_before_first_taper": weeks_before_first_taper,
            "peak_weekly_cap_lookahead": lookahead,
            "peak_weekly_cap_applied": apply_peak_weekly_cap,
            "is_cutback": is_cutback,
            "rebuild_after_cutback": rebuild_after_cutback,
            "volume_cap_kind": volume_cap_kind,
            "long_run": long_run,
            "prev_long_run": prev_long_run,
            "lr_down_vs_prev": lr_down,
            "total_up_vs_prev_despite_lr_down": total_up_despite_lr_down,
            "prev_week_total": prev_week_total,
            "prev_prev_week_total": prev_prev_week_total,
            "runs_per_week": runs_per_week,
            "base_total": base_total,
            "min_total": min_total,
            "max_total": max_total,
            "after_lr_clamp": after_lr_clamp,
            "after_volume_cap": after_volume_cap,
            "after_min_viable": after_min_viable,
            "after_peak_cap": after_peak_cap,
            "after_starting_adj": after_starting_adj,
            "after_min_viable_post_starting": after_min_viable_post_starting,
            "after_phase_cap": after_phase_cap,
            "after_peak_taper": after_peak_taper,
            "before_round": before_round,
            "after_round": float(rounded),
            "largest_abs_step": largest_edge,
            "largest_abs_delta": largest_abs,
        }
        logger.debug("%s", json.dumps(trace, default=str))

    # CRITICAL: Always round to whole miles for internal consistency
    # Frontend will convert to km for display using toDisplayDistance()
    # This prevents metric plans from diverging due to rounding differences
    return rounded


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
    prev_phase: Optional[str] = None
    prev_long_run: Optional[float] = None
    rebuild_next_week = False
    starting_mileage_adjustment = (
        scenario_adjustments.get("starting_mileage_adjustment", 1.0)
        if scenario_adjustments
        else 1.0
    )

    first_taper_week = _first_taper_week_number(weeks)

    for week in weeks:
        week_num = week.get("week_number", 0)
        long_run = float(week.get("long_run_miles", 0) or 0)
        phase = week.get("phase")

        weeks_before_taper: Optional[int] = None
        if (
            first_taper_week is not None
            and week_num > 0
            and phase is not None
            and not _phase_is_taper(phase)
        ):
            weeks_before_taper = int(first_taper_week) - int(week_num)

        if long_run > 0:
            cutback_flag: Optional[bool]
            if "is_cutback" in week:
                cutback_flag = bool(week.get("is_cutback"))
            else:
                cutback_flag = None
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
                prev_phase=prev_phase,
                unit_system=unit_system,
                week_number=week_num,
                prev_long_run=prev_long_run,
                is_cutback=cutback_flag,
                weeks_before_first_taper=weeks_before_taper,
            )
            prev_prev_total = prev_total
            prev_total = float(total)
            prev_long_run = long_run
        else:
            total = 0
            prev_prev_total = prev_total
            prev_total = None
            prev_long_run = None

        prev_phase = week.get("phase")

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
