"""
Micro-Stretch Service

Purpose:
    If user has extra time before race date (buffer weeks), spread out the increases
    in Base/Build phases by reducing week-to-week jumps from 2-3 miles to ~1 mile.
    This makes progression more gradual without changing peak/taper timing.

Design:
    - Only applies if buffer weeks > 0
    - Modifies Base/Build phases (pre-peak weeks)
    - Keeps peak and taper phases unchanged
    - Reduces jumps gradually: spreads increases over available buffer
"""

from typing import Any, Dict, List, Tuple
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.utils.timezone_helpers import DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)


def micro_stretch_plan(
    weeks: List[Dict[str, Any]],
    buffer_weeks: float,
    min_buffer_threshold: float = 1.0,
) -> List[Dict[str, Any]]:
    """Apply micro-stretch to spread increases in Base/Build phases.

    Args:
        weeks: List of weeks with week_number, phase, long_run_miles, weekly_mileage
        buffer_weeks: Number of extra weeks available (weeks_available - weeks_needed)
        min_buffer_threshold: Minimum buffer weeks required to apply stretch (default 1.0)

    Returns:
        Modified weeks list with spread-out increases
    """
    if buffer_weeks < min_buffer_threshold:
        # Not enough buffer to stretch
        return weeks

    if not weeks:
        return weeks

    # Find peak week (highest long run)
    peak_idx = 0
    peak_lr = 0.0
    for i, w in enumerate(weeks):
        lr = float(w.get("long_run_miles", 0) or 0)
        if lr > peak_lr:
            peak_lr = lr
            peak_idx = i

    # Identify Base/Build phase (everything before peak + 1 week after peak)
    # We'll stretch the pre-peak weeks
    pre_peak_weeks = weeks[: peak_idx + 1]  # Include peak week

    if len(pre_peak_weeks) < 2:
        # Not enough weeks to stretch
        return weeks

    # Calculate average jump size in Base/Build
    jumps = []
    for i in range(1, len(pre_peak_weeks)):
        prev_lr = float(pre_peak_weeks[i - 1].get("long_run_miles", 0) or 0)
        curr_lr = float(pre_peak_weeks[i].get("long_run_miles", 0) or 0)
        if curr_lr > prev_lr:
            jumps.append((i, curr_lr - prev_lr))

    if not jumps:
        # No increases to stretch
        return weeks

    avg_jump = sum(j[1] for j in jumps) / len(jumps) if jumps else 1.0

    # If average jump is already <= 1.0, no need to stretch
    if avg_jump <= 1.1:
        return weeks

    # Calculate how many weeks we can stretch into
    # Use up to buffer_weeks to spread increases
    stretch_weeks = min(int(buffer_weeks), len(jumps))

    if stretch_weeks <= 0:
        return weeks

    # Create stretched version by reducing jumps in Base/Build phases
    stretched = []

    for i, week in enumerate(weeks):
        new_week = week.copy()

        if i <= peak_idx and i > 0:
            # This is a Base/Build week after the first week
            prev_lr = float(
                stretched[i - 1].get("long_run_miles", 0)
                if stretched
                else float(weeks[i - 1].get("long_run_miles", 0) or 0)
            )
            curr_lr = float(week.get("long_run_miles", 0) or 0)

            if curr_lr > prev_lr:
                # This is an increase week - reduce the jump to ~1.0 mile
                original_jump = curr_lr - prev_lr

                # Target: reduce jumps to ~1.0 mile (or keep as is if already <= 1.0)
                if original_jump > 1.0:
                    # Reduce jump to ~1.0 mile (allow 0.5-1.5 range for flexibility)
                    target_jump = min(1.5, max(0.5, 1.0))
                    new_lr = prev_lr + target_jump
                else:
                    # Already small jump, keep it
                    new_lr = curr_lr

                # Round to 0.5
                new_lr = round(new_lr * 2) / 2.0

                # Ensure we don't go backwards
                new_lr = max(prev_lr + 0.5, new_lr)

                # Ensure we don't exceed original peak
                new_lr = min(new_lr, peak_lr)

                new_week["long_run_miles"] = new_lr

                # Adjust weekly_mileage proportionally (maintain LR % of total)
                if week.get("weekly_mileage"):
                    original_total = float(week.get("weekly_mileage", 0) or 0)
                    if original_total > 0:
                        # Calculate LR percentage
                        lr_pct = (
                            curr_lr / original_total if original_total > 0 else 0.30
                        )
                        # Recalculate total with new LR
                        new_total = new_lr / lr_pct if lr_pct > 0 else new_lr * 2.5
                        new_week["weekly_mileage"] = round(new_total * 2) / 2.0
                    else:
                        new_week["weekly_mileage"] = new_lr * 2.5  # Fallback

                stretched.append(new_week)
            else:
                # Cutback or no change - keep as is
                stretched.append(new_week)
        else:
            # Peak week or taper weeks - keep as is
            stretched.append(new_week)

    # Re-adjust weekly totals to maintain LR percentage (if needed)
    from src.services.training_plan.weekly_total_calculator import (
        calculate_weekly_totals_from_long_runs,
    )

    # Recalculate totals for stretched weeks
    if any("weekly_mileage" in w for w in stretched):
        # Get training days (assume 4 days/week if not available)
        runs_per_week = 4  # Default
        stretched_with_totals = calculate_weekly_totals_from_long_runs(
            weeks=stretched,
            runs_per_week=runs_per_week,
        )
        return stretched_with_totals

    logger.info(
        f"Micro-stretched plan: {len(jumps)} jumps spread across {stretch_weeks} weeks"
    )
    return stretched


def _get_local_today(timezone_str: str) -> date:
    try:
        tz = ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Unknown timezone '%s' provided for micro stretch. Falling back to %s.",
            timezone_str,
            DEFAULT_TIMEZONE,
        )
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).date()


def apply_micro_stretch_if_needed(
    weeks: List[Dict[str, Any]],
    race_date: Any,
    plan_start_date: Any = None,
    timezone_str: str = DEFAULT_TIMEZONE,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Apply micro-stretch if there's buffer time, and return metadata.

    Args:
        weeks: List of weeks
        race_date: Race date
        plan_start_date: Plan start date (if None, calculates from today)

    Returns:
        (stretched_weeks, metadata) where metadata includes:
        - stretched: bool
        - buffer_weeks: float
        - original_weeks: int
    """
    # Calculate buffer
    if isinstance(race_date, str):
        rd = datetime.fromisoformat(race_date.split("T")[0]).date()
    elif isinstance(race_date, date):
        rd = race_date
    else:
        rd = None

    if not rd:
        return weeks, {
            "stretched": False,
            "buffer_weeks": 0.0,
            "original_weeks": len(weeks),
        }

    today_local = _get_local_today(timezone_str)

    if plan_start_date:
        if isinstance(plan_start_date, str):
            start_d = datetime.fromisoformat(plan_start_date.split("T")[0]).date()
        elif isinstance(plan_start_date, date):
            start_d = plan_start_date
        else:
            start_d = today_local
    else:
        # Default: next Monday
        from src.utils.date_helpers import get_next_monday

        start_d = get_next_monday(today_local, include_today=True)

    weeks_needed = len(weeks)
    weeks_available = (rd - start_d).days / 7.0
    buffer_weeks = weeks_available - weeks_needed

    metadata = {
        "stretched": False,
        "buffer_weeks": buffer_weeks,
        "original_weeks": len(weeks),
        "weeks_needed": weeks_needed,
        "weeks_available": weeks_available,
    }

    if buffer_weeks > 1.0:  # Only stretch if at least 1 week buffer
        stretched_weeks = micro_stretch_plan(weeks, buffer_weeks)
        metadata["stretched"] = True
        metadata["stretched_weeks"] = len(stretched_weeks)
        return stretched_weeks, metadata

    return weeks, metadata
