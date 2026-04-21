"""
Pace Adjustments

Adjust pace zones based on weekly feedback (RPE, completion).
"""

import logging
from dataclasses import dataclass
from typing import List

from src.utils.run_type_constants import RUN_TYPE_EASY, RUN_TYPE_STEADY

from .models import PaceSeed
from .validation import validate_pace_seed

logger = logging.getLogger(__name__)


@dataclass
class WeekLogRun:
    """Single run log entry."""

    run_type: str  # "easy", "steady", "long", etc.
    planned_mi: float
    done_mi: float
    rpe: int  # 1-10 scale
    avg_hr: int = None  # Optional average heart rate


def adjust_pace_seed(
    seed: PaceSeed,
    week_log: List[WeekLogRun],
) -> tuple[PaceSeed, bool]:
    """
    Adjust pace seed based on week completion logs.

    Args:
        seed: Current PaceSeed to adjust
        week_log: List of WeekLogRun entries from the week

    Returns:
        (adjusted_seed, disable_quality_workouts)
        - adjusted_seed: New PaceSeed with adjusted paces
        - disable_quality_workouts: True if quality workouts should be disabled

    Raises:
        ValueError: If seed is invalid
        RuntimeError: If adjusted seed fails validation
    """
    # Validate input seed
    is_valid, error_msg = validate_pace_seed(seed)
    if not is_valid:
        logger.error(f"Invalid input seed for adjustment: {error_msg}")
        raise ValueError(f"Invalid input seed: {error_msg}")

    if not week_log:
        logger.debug("No week log provided, returning seed unchanged")
        return (seed, False)

    logger.info(f"Adjusting pace seed based on {len(week_log)} week log entries")

    # Calculate metrics
    completion_rate = _calculate_completion_rate(week_log)
    avg_rpe = _calculate_avg_rpe(week_log)

    logger.debug(
        f"Week metrics: completion_rate={completion_rate:.2%}, avg_rpe={avg_rpe:.1f}"
    )

    # Adjustment rules
    adjusted_seed = None
    disable_quality = False

    if completion_rate < 0.6:
        adjusted_seed = _adjust_all_paces(seed, +15)
        disable_quality = True
        logger.info(
            f"Low completion ({completion_rate:.1%}): "
            f"slowing all paces by 15s/mi, disabling quality workouts"
        )
    elif avg_rpe <= 2.0 and completion_rate >= 0.8:
        adjusted_seed = _adjust_all_paces(seed, -5)
        disable_quality = False
        logger.info(
            f"Excellent recovery (RPE={avg_rpe:.1f}, completion={completion_rate:.1%}): "
            f"speeding all paces by 5s/mi"
        )
    elif avg_rpe >= 5.0:
        adjusted_seed = _adjust_all_paces(seed, +10)
        disable_quality = True
        logger.info(
            f"High RPE ({avg_rpe:.1f}): "
            f"slowing all paces by 10s/mi, disabling quality workouts"
        )
    else:
        logger.debug("No adjustment needed (normal week)")
        return (seed, False)

    # Validate adjusted seed
    is_valid, error_msg = validate_pace_seed(adjusted_seed)
    if not is_valid:
        logger.error(f"Adjusted seed failed validation: {error_msg}")
        raise RuntimeError(f"Adjusted seed failed validation: {error_msg}")

    return (adjusted_seed, disable_quality)


def _calculate_completion_rate(week_log: List[WeekLogRun]) -> float:
    """Calculate completion rate for the week."""
    total_planned = sum(r.planned_mi for r in week_log)
    total_done = sum(r.done_mi for r in week_log)
    return total_done / max(1e-6, total_planned)


def _calculate_avg_rpe(week_log: List[WeekLogRun]) -> float:
    """Calculate average RPE for easy/steady runs."""
    easy_rpe = [
        r.rpe for r in week_log if r.run_type in (RUN_TYPE_EASY, RUN_TYPE_STEADY)
    ]
    return sum(easy_rpe) / len(easy_rpe) if easy_rpe else 3.0


def _adjust_all_paces(seed: PaceSeed, delta_sec: float) -> PaceSeed:
    """Adjust all pace zones by delta_sec."""
    return PaceSeed(
        E_min=seed.E_min + delta_sec,
        E_max=seed.E_max + delta_sec,
        S_min=seed.S_min + delta_sec,
        S_max=seed.S_max + delta_sec,
        M=seed.M + delta_sec,
        T_min=seed.T_min + delta_sec,
        T_max=seed.T_max + delta_sec,
        week1_long_cap=seed.week1_long_cap,
    )
