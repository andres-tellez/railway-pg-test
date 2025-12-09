"""
Pace Adjustments

Adjust pace zones based on weekly feedback (RPE, completion).
"""
from dataclasses import dataclass
from typing import List

from .models import PaceSeed

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
    
    Returns:
        (adjusted_seed, disable_quality_workouts)
    """
    if not week_log:
        return (seed, False)
    
    # Calculate metrics
    completion_rate = _calculate_completion_rate(week_log)
    avg_rpe = _calculate_avg_rpe(week_log)
    
    # Adjustment rules
    if completion_rate < 0.6:
        return (_adjust_all_paces(seed, +15), True)
    
    if avg_rpe <= 2.0 and completion_rate >= 0.8:
        return (_adjust_all_paces(seed, -5), False)
    
    if avg_rpe >= 5.0:
        return (_adjust_all_paces(seed, +10), True)
    
    return (seed, False)


def _calculate_completion_rate(week_log: List[WeekLogRun]) -> float:
    """Calculate completion rate for the week."""
    total_planned = sum(r.planned_mi for r in week_log)
    total_done = sum(r.done_mi for r in week_log)
    return total_done / max(1e-6, total_planned)


def _calculate_avg_rpe(week_log: List[WeekLogRun]) -> float:
    """Calculate average RPE for easy/steady runs."""
    easy_rpe = [r.rpe for r in week_log if r.run_type in ("easy", "steady")]
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

