"""
Weekly Adjuster Service

Purpose:
    Adjust pace zones based on week completion logs (completion rate + RPE, optionally HR).
    Used in rolling mode to adapt paces weekly based on runner feedback.

Integration:
    Called when rebuilding upcoming week in rolling mode.
    Takes previous week's logs (from database or user input) and adjusts pace zones.

Author: SmartCoach Development Team
Last Updated: January 2026
"""

from dataclasses import dataclass
from typing import List

from src.smartcoach_mobile_coach.runner_profile.models import (
    PaceZoneBand,
    PaceZoneComputation,
)
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_EASY,
    RUN_TYPE_STEADY,
)


@dataclass
class WeekLogRun:
    """Single run log entry."""

    run_type: str  # "easy", "steady", "long", etc.
    planned_mi: float
    done_mi: float
    rpe: int  # 1-10 scale
    avg_hr: int = None  # Optional average heart rate


def _shift_band(band: PaceZoneBand, delta_sec: float) -> PaceZoneBand:
    low_sec = int(round(band.low_sec + delta_sec))
    high_sec = int(round(band.high_sec + delta_sec))
    if low_sec < 0:
        low_sec = 0
    if high_sec < low_sec:
        high_sec = low_sec
    return PaceZoneBand(
        low_sec=low_sec,
        high_sec=high_sec,
        display=band.display,
    )


def _shift_pace_zones(
    pace_zones: PaceZoneComputation,
    delta_sec: float,
) -> PaceZoneComputation:
    return PaceZoneComputation(
        pace_z2=_shift_band(pace_zones.pace_z2, delta_sec),
        pace_z3=_shift_band(pace_zones.pace_z3, delta_sec),
        pace_z4=_shift_band(pace_zones.pace_z4, delta_sec),
        pace_source=pace_zones.pace_source,
        pace_computed_at=pace_zones.pace_computed_at,
        marathon_sec=max(0, int(round(pace_zones.marathon_sec + delta_sec))),
        week1_long_cap=pace_zones.week1_long_cap,
    )


def _calculate_completion_rate(week_log: List[WeekLogRun]) -> float:
    total_planned = sum(r.planned_mi for r in week_log)
    total_done = sum(r.done_mi for r in week_log)
    return total_done / max(1e-6, total_planned)


def _calculate_avg_rpe(week_log: List[WeekLogRun]) -> float:
    easy_rpe = [
        r.rpe for r in week_log if r.run_type in (RUN_TYPE_EASY, RUN_TYPE_STEADY)
    ]
    return sum(easy_rpe) / len(easy_rpe) if easy_rpe else 3.0


def adjust_pace_zones_from_week(
    pace_zones: PaceZoneComputation,
    week_log: List[WeekLogRun],
) -> tuple[PaceZoneComputation, bool]:
    """
    Adjust pace zones from weekly completion and perceived effort.

    Returns:
        (adjusted_pace_zones, disable_quality_workouts)
    """
    if not week_log:
        return pace_zones, False

    completion_rate = _calculate_completion_rate(week_log)
    avg_rpe = _calculate_avg_rpe(week_log)

    if completion_rate < 0.6:
        return _shift_pace_zones(pace_zones, +15), True
    if avg_rpe <= 2.0 and completion_rate >= 0.8:
        return _shift_pace_zones(pace_zones, -5), False
    if avg_rpe >= 5.0:
        return _shift_pace_zones(pace_zones, +10), True
    return pace_zones, False
