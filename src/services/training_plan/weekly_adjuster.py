"""
Weekly Adjuster Service

Purpose:
    Adjust pace seed based on week completion logs (completion rate + RPE, optionally HR).
    Used in rolling mode to adapt paces weekly based on runner feedback.

Integration:
    Called when rebuilding upcoming week in rolling mode.
    Takes previous week's logs (from database or user input) and adjusts pace zones.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
import logging

from .pace_seed_service import PaceSeed, _time_add

logger = logging.getLogger(__name__)


@dataclass
class WeekLogRun:
    """Log entry for a single run in a week."""

    run_type: str  # "easy"/"steady"/"endurance"/"long"
    planned_mi: float
    done_mi: float
    rpe: int  # 1-10 scale (Rate of Perceived Exertion)
    avg_hr: Optional[int] = None  # Optional average heart rate


def adjust_seed_from_week(
    seed: PaceSeed, week_log: List[WeekLogRun]
) -> tuple[PaceSeed, bool]:
    """
    Adjust pace seed based on week completion logs.

    Args:
        seed: Current PaceSeed to adjust
        week_log: List of runs completed in the week

    Returns:
        Tuple of (adjusted_seed, disable_quality_next_week)
        - adjusted_seed: New PaceSeed with adjusted paces
        - disable_quality_next_week: True if quality workouts should be skipped

    Logic:
        - Low completion (<60%) → slow everything +15s, disable quality
        - Very easy (RPE ≤2) + good completion (≥80%) → slightly faster -5s
        - Too hard (RPE ≥5) → slow everything +10s, disable quality
    """
    if not week_log:
        logger.debug("No week log provided, returning seed unchanged")
        return (seed, False)

    # Calculate completion rate
    total_planned = sum(r.planned_mi for r in week_log)
    total_done = sum(r.done_mi for r in week_log)
    completed = total_done / max(1e-6, total_planned)

    # Calculate average RPE for easy/steady runs (these indicate base fitness)
    easy_rpe = [r.rpe for r in week_log if r.run_type in ("easy", "steady")]
    rpe_avg = sum(easy_rpe) / len(easy_rpe) if easy_rpe else 3.0

    logger.info(
        f"Week adjustment: completion={completed:.1%}, avg_RPE={rpe_avg:.1f} "
        f"(easy/steady runs: {len(easy_rpe)})"
    )

    # Create new seed (copy)
    new = PaceSeed(*seed.__dict__.values())
    disable_quality = False

    # Adjustment 1: Low completion → slow everything down
    if completed < 0.6:
        delta = +15  # Slow by 15 seconds per mile
        new = PaceSeed(
            E_min=_time_add(seed.E_min, delta),
            E_max=_time_add(seed.E_max, delta),
            S_min=_time_add(seed.S_min, delta),
            S_max=_time_add(seed.S_max, delta),
            M=_time_add(seed.M, delta),
            T_min=_time_add(seed.T_min, delta),
            T_max=_time_add(seed.T_max, delta),
            week1_long_cap=seed.week1_long_cap,
        )
        disable_quality = True
        logger.info(
            f"Low completion ({completed:.1%}): slowing all paces by {delta}s, disabling quality"
        )
        return (new, disable_quality)

    # Adjustment 2: Very easy + good completion → slightly faster (runner is fitter)
    if rpe_avg <= 2.0 and completed >= 0.8:
        delta = -5  # Speed up by 5 seconds per mile
        new = PaceSeed(
            E_min=_time_add(seed.E_min, delta),
            E_max=_time_add(seed.E_max, delta),
            S_min=_time_add(seed.S_min, delta),
            S_max=_time_add(seed.S_max, delta),
            M=_time_add(seed.M, delta),
            T_min=_time_add(seed.T_min, delta),
            T_max=_time_add(seed.T_max, delta),
            week1_long_cap=seed.week1_long_cap,
        )
        logger.info(
            f"Very easy effort (RPE={rpe_avg:.1f}) + good completion: speeding up by {delta}s"
        )
        return (new, disable_quality)

    # Adjustment 3: Too hard (RPE ≥5) → slow everything down
    if rpe_avg >= 5.0:
        delta = +10  # Slow by 10 seconds per mile
        new = PaceSeed(
            E_min=_time_add(seed.E_min, delta),
            E_max=_time_add(seed.E_max, delta),
            S_min=_time_add(seed.S_min, delta),
            S_max=_time_add(seed.S_max, delta),
            M=_time_add(seed.M, delta),
            T_min=_time_add(seed.T_min, delta),
            T_max=_time_add(seed.T_max, delta),
            week1_long_cap=seed.week1_long_cap,
        )
        disable_quality = True
        logger.info(
            f"Too hard effort (RPE={rpe_avg:.1f}): slowing all paces by {delta}s, disabling quality"
        )
        return (new, disable_quality)

    # No adjustment needed
    logger.debug("No adjustment needed based on week log")
    return (new, disable_quality)


if __name__ == "__main__":
    # Quick test
    from .pace_seed_service import get_initial_pace_seed

    # Create a test seed
    seed = PaceSeed(
        E_min=600.0,
        E_max=690.0,
        S_min=570.0,
        S_max=630.0,
        M=540.0,
        T_min=510.0,
        T_max=520.0,
        week1_long_cap=8.0,
    )

    # Test adjustment with low completion
    week_log = [
        WeekLogRun(run_type="easy", planned_mi=4.0, done_mi=2.0, rpe=4),
        WeekLogRun(run_type="steady", planned_mi=5.0, done_mi=2.0, rpe=5),
        WeekLogRun(run_type="long", planned_mi=8.0, done_mi=4.0, rpe=6),
    ]

    new_seed, disable = adjust_seed_from_week(seed, week_log)
    print(
        f"Adjusted: E={new_seed.E_min:.1f}-{new_seed.E_max:.1f}s/mi, disable_quality={disable}"
    )
