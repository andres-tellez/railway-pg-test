"""
Recovery Week Insertion Service

Purpose:
    If the generated plan is shorter than available weeks until race date,
    insert recovery weeks evenly throughout the Build/Peak phases.

    Each recovery week:
    - Copy of previous week
    - Total mileage reduced by 15%
    - Long run reduced by ~3 miles
    - Phase set to "Recovery"

Design:
    - Only applies if plan_weeks < target_weeks (available weeks)
    - Distributes recovery weeks evenly after every 2-3 build/peak weeks
    - Preserves peak and taper timing
"""

from typing import Any, Dict, List, Tuple
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.utils.timezone_helpers import DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)


def find_insertion_points(weeks: List[Dict[str, Any]], extra_weeks: int) -> List[int]:
    """Find where to insert recovery weeks.

    Distributes evenly throughout Build/Peak phases (after every 2-3 weeks).

    Args:
        weeks: List of weeks
        extra_weeks: Number of weeks to insert

    Returns:
        List of indices where to insert (after this index)
    """
    if extra_weeks <= 0:
        return []

    # Find Build and Peak weeks (exclude Base and Taper)
    build_peak_indices = []
    for i, week in enumerate(weeks):
        phase = week.get("phase", "").lower()
        if phase in ("build", "peak", "specific"):
            build_peak_indices.append(i)

    if not build_peak_indices:
        # No build/peak weeks, insert at end before taper
        taper_start = max(0, len(weeks) - 3)  # Assume last 3 weeks are taper
        return [max(0, taper_start) for _ in range(extra_weeks)]

    # Distribute evenly: after every 2-3 build/peak weeks
    # Strategy: Calculate spacing to distribute all extra_weeks evenly
    insertion_points = []

    if len(build_peak_indices) == 0:
        # No build/peak weeks, insert before taper
        taper_start = max(0, len(weeks) - 3)
        return [taper_start] * extra_weeks

    # Calculate how to distribute extra_weeks across build_peak_indices
    # We want to insert after every 2-3 build/peak weeks
    # Calculate spacing: if we have N build/peak weeks and need M insertions,
    # space them evenly (every N/M build/peak weeks)

    if extra_weeks >= len(build_peak_indices):
        # More weeks to insert than build/peak weeks - insert after every build/peak week
        # and add remaining before taper
        insertion_points = build_peak_indices.copy()
        remaining = extra_weeks - len(build_peak_indices)
        if remaining > 0:
            taper_start = max(0, len(weeks) - 3)
            for i in range(remaining):
                insertion_points.append(max(0, taper_start - i))
    else:
        # Fewer or equal weeks to insert - space them evenly
        # Calculate spacing: every N/M build/peak weeks
        spacing = max(2, len(build_peak_indices) // (extra_weeks + 1))

        for i in range(extra_weeks):
            # Calculate position: after every spacing build/peak weeks
            pos = (i + 1) * spacing
            if pos < len(build_peak_indices):
                insertion_points.append(build_peak_indices[pos])
            else:
                # Insert before taper if we've covered all build/peak weeks
                taper_start = max(0, len(weeks) - 3)
                insertion_points.append(max(0, taper_start - (extra_weeks - i)))

    # Ensure we have exactly extra_weeks insertion points
    while len(insertion_points) < extra_weeks:
        # Add more before taper
        taper_start = max(0, len(weeks) - 3)
        candidate = max(0, taper_start - (extra_weeks - len(insertion_points)))
        if candidate not in insertion_points:
            insertion_points.append(candidate)
        else:
            # Already exists, add one before
            insertion_points.append(max(0, candidate - 1))

    # Limit to exactly extra_weeks
    insertion_points = insertion_points[:extra_weeks]

    return sorted(set(insertion_points))  # Remove duplicates and sort


def create_recovery_week(previous_week: Dict[str, Any]) -> Dict[str, Any]:
    """Create a recovery week based on previous week.

    Args:
        previous_week: Week to base recovery week on

    Returns:
        New recovery week dict
    """
    from copy import deepcopy

    recovery = deepcopy(previous_week)

    from src.services.training_plan.v2.shared_v2.rounding_utils import (
        round_to_half_mile,
    )

    # Reduce total mileage by 15%
    original_total = float(recovery.get("weekly_mileage", 0) or 0)
    new_total = round_to_half_mile(original_total * 0.85)

    # Reduce long run by ~3 miles (or 20%, whichever is less)
    original_lr = float(recovery.get("long_run_miles", 0) or 0)
    lr_reduction = min(3.0, original_lr * 0.20)  # Max 3 miles or 20%, whichever is less
    new_lr = round_to_half_mile(original_lr - lr_reduction)

    # Ensure minimums
    new_lr = max(3.0, new_lr)  # At least 3 miles
    new_total = max(new_lr * 1.5, new_total)  # Total must be > LR

    # Update week
    recovery["weekly_mileage"] = new_total
    recovery["long_run_miles"] = new_lr
    recovery["phase"] = "Recovery"

    # Update week_number (will be corrected when inserted)
    # Keep workouts but will need recalculation
    if "workouts" in recovery:
        # Recalculate workouts with new totals
        recovery["workouts"] = []  # Clear - will be recalculated

    return recovery


def insert_recovery_weeks(
    weeks: List[Dict[str, Any]],
    extra_weeks: int,
) -> List[Dict[str, Any]]:
    """Insert recovery weeks into plan.

    Args:
        weeks: Original plan weeks
        extra_weeks: Number of recovery weeks to insert

    Returns:
        Modified weeks list with recovery weeks inserted
    """
    if extra_weeks <= 0:
        return weeks

    # Find insertion points
    insertion_points = find_insertion_points(weeks, extra_weeks)

    if not insertion_points:
        # Fallback: insert before taper
        taper_start = max(0, len(weeks) - 3)
        insertion_points = [taper_start] * extra_weeks

    # Sort insertion points (descending) to insert from end to beginning
    # This avoids index shifting issues
    insertion_points.sort(reverse=True)

    modified_weeks = weeks.copy()

    # Ensure we have exactly extra_weeks insertion points
    if len(insertion_points) < extra_weeks:
        # Fill remaining before taper
        taper_start = max(0, len(weeks) - 3)
        while len(insertion_points) < extra_weeks:
            candidate = max(0, taper_start - (extra_weeks - len(insertion_points)))
            if candidate not in insertion_points:
                insertion_points.append(candidate)
            else:
                insertion_points.append(max(0, candidate - 1))

    # Limit to exactly extra_weeks
    insertion_points = insertion_points[:extra_weeks]

    # Sort in reverse to insert from end to beginning (avoids index shifting)
    insertion_points.sort(reverse=True)

    inserted_count = 0
    for insert_after_idx in insertion_points:
        if insert_after_idx < len(modified_weeks):
            # Get the week to base recovery on
            previous_week = modified_weeks[insert_after_idx]

            # Create recovery week
            recovery_week = create_recovery_week(previous_week)

            # Insert after this index
            modified_weeks.insert(insert_after_idx + 1, recovery_week)
            inserted_count += 1

    # Renumber weeks
    for i, week in enumerate(modified_weeks):
        week["week_number"] = i + 1

    logger.info(
        f"Inserted {inserted_count} recovery weeks into plan (requested {extra_weeks})"
    )

    if inserted_count < extra_weeks:
        logger.warning(
            f"Only inserted {inserted_count} of {extra_weeks} requested recovery weeks"
        )

    return modified_weeks


def _get_local_today(timezone_str: str) -> date:
    try:
        tz = ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Unknown timezone '%s' provided. Falling back to %s.",
            timezone_str,
            DEFAULT_TIMEZONE,
        )
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(tz).date()


def apply_recovery_week_insertion_if_needed(
    weeks: List[Dict[str, Any]],
    race_date: Any,
    plan_start_date: Any = None,
    timezone_str: str = DEFAULT_TIMEZONE,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Apply recovery week insertion if plan is shorter than available weeks.

    Args:
        weeks: List of weeks
        race_date: Race date
        plan_start_date: Plan start date (if None, calculates from today)
        timezone_str: IANA timezone string representing the user's local time

    Returns:
        (modified_weeks, metadata) where metadata includes:
        - inserted: bool
        - extra_weeks: int
        - original_weeks: int
        - target_weeks: float
    """
    # Calculate target weeks (available weeks)
    if isinstance(race_date, str):
        rd = datetime.fromisoformat(race_date.split("T")[0]).date()
    elif isinstance(race_date, date):
        rd = race_date
    else:
        rd = None

    if not rd:
        return weeks, {
            "inserted": False,
            "extra_weeks": 0,
            "original_weeks": len(weeks),
            "target_weeks": 0.0,
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
        # Default: Monday of the calendar week containing "today" (Mon–Sun week).
        # Note: get_next_monday(..., include_today=True) on Sunday points at *next* Monday,
        # which would skip the in-progress week — use week start instead.
        from src.utils.date_helpers import get_week_start_for_date

        start_d = get_week_start_for_date(today_local)

    current_plan_weeks = len(weeks)

    # Calculate target weeks ensuring the week containing race day is included.
    # OLD LOGIC (BUGGY):
    #   target_weeks = (rd - start_d).days / 7.0
    #   Problem: If race day is Saturday and plan ends earlier, fractional calculation
    #            might not include the race week (e.g., 14.86 weeks - 14 = 0.86 → int(0.86) = 0)
    #
    # NEW LOGIC (FIXED):
    #   Calculate Monday of week containing race day, then calculate weeks to that Monday.
    #   Use ceiling to ensure we include the complete week containing race day.
    #   This ensures the plan always includes the week containing race day.
    import math

    # Calculate Monday of the week containing race day
    race_day_weekday = rd.weekday()  # 0=Monday, 6=Sunday
    monday_of_race_week = rd - timedelta(days=race_day_weekday)

    # Calculate weeks from start to Monday of race week
    days_to_race_week_monday = (monday_of_race_week - start_d).days
    weeks_to_race_week = days_to_race_week_monday / 7.0

    # We need AT LEAST ceil(weeks_to_race_week) weeks to reach the race week
    # Plus 1 to include the race week itself (since weeks are 0-indexed from start)
    # Example: If Monday of race week is 98 days from start = 14 weeks exactly,
    #          we need 15 total weeks (14 to reach it + 1 for the race week itself)
    target_weeks = math.ceil(weeks_to_race_week) + 1

    extra_weeks = int(target_weeks - current_plan_weeks)

    metadata = {
        "inserted": False,
        "extra_weeks": extra_weeks,
        "original_weeks": current_plan_weeks,
        "target_weeks": target_weeks,
    }

    # Only insert if we have extra weeks (plan is shorter than available)
    if extra_weeks > 0:
        modified_weeks = insert_recovery_weeks(weeks, extra_weeks)
        metadata["inserted"] = True
        metadata["final_weeks"] = len(modified_weeks)

        # Recalculate workouts for new weeks (need to regenerate Pass 3)
        # This will be done in the route after insertion

        return modified_weeks, metadata

    return weeks, metadata
