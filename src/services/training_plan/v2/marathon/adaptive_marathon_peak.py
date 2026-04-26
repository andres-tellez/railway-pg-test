"""
Adaptive marathon peak long-run target.

Replaces a single fixed peak (e.g. 20 mi) with a banded target from weekly volume,
primary goal, and calendar length so validation matches runner readiness.
"""

from __future__ import annotations

from typing import Any, Optional

from src.schemas.plan_schema import PrimaryGoal
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig


class RaceConfigPeakOverride:
    """
    Delegates to a base RaceDistanceConfig but overrides peak miles and a safe
    pre-taper cap (must stay strictly below peak).
    """

    __slots__ = ("_base", "_peak_miles")

    def __init__(self, base: RaceDistanceConfig, peak_miles: float) -> None:
        self._base = base
        self._peak_miles = float(peak_miles)

    @property
    def target_peak_miles(self) -> float:
        return self._peak_miles

    @property
    def pre_taper_cap_miles(self) -> float:
        base_cap = self._base.pre_taper_cap_miles
        peak = self._peak_miles
        upper = max(self._base.min_long_run_miles, peak - 1.0)
        return min(base_cap, upper)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def _goal_is_just_finish(primary_goal: Optional[str]) -> bool:
    if not primary_goal:
        return False
    s = str(primary_goal).strip().lower()
    if s == PrimaryGoal.JUST_FINISH.value.lower():
        return True
    return "just" in s and "finish" in s


def _goal_is_target_time(primary_goal: Optional[str]) -> bool:
    if not primary_goal:
        return False
    s = str(primary_goal).strip().lower()
    if s == PrimaryGoal.TARGET_TIME.value.lower():
        return True
    return "target" in s and "time" in s


def resolve_marathon_adaptive_target_peak_miles(
    *,
    weekly_mileage: float,
    primary_goal: Optional[str],
    plan_length_weeks: Optional[int],
) -> float:
    """
    Marathon peak long run (miles).

    Volume bands (typical target range):
        weekly_mileage < 40  -> 16–18 mi
        40 <= weekly_mileage <= 55 -> 18–20 mi
        weekly_mileage > 55 -> 20 mi

    Within a band, \"Just Finish\" biases lower, \"Target Time\" biases higher.
    Short calendars nudge the peak down (floored slightly below the band low when needed).
    """
    mpw = float(weekly_mileage or 0.0)
    pw = plan_length_weeks

    if mpw < 40.0:
        lo, hi = 16.0, 18.0
    elif mpw <= 55.0:
        lo, hi = 18.0, 20.0
    else:
        lo, hi = 20.0, 20.0

    span = hi - lo
    if span <= 0:
        peak = hi
    else:
        position = 0.5
        if _goal_is_just_finish(primary_goal):
            position = 0.2
        elif _goal_is_target_time(primary_goal):
            position = 0.82
        peak = lo + position * span

    if pw and pw > 0:
        if pw <= 12:
            peak -= 1.5
        elif pw <= 14:
            peak -= 1.0
        elif pw <= 16:
            peak -= 0.5

    floor_miles = max(15.0, lo - 1.0)
    peak = max(floor_miles, min(hi, peak))
    peak = round(peak * 2.0) / 2.0
    peak = max(floor_miles, min(hi, peak))
    return float(peak)
