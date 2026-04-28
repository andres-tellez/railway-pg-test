"""
Adaptive marathon peak long-run target.

Replaces a single fixed peak (e.g. 20 mi) with a banded target from weekly volume,
primary goal, and calendar length so validation matches runner readiness.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.schemas.plan_schema import PrimaryGoal
from src.services.training_plan.v2.race_configs.base_config import RaceDistanceConfig

# Peak weekly caps (must match ``MarathonConfig.peak_caps``) for callers that omit ``peak_caps``.
_DEFAULT_MARATHON_PEAK_CAPS: Dict[int, int] = {
    3: 42,
    4: 46,
    5: 50,
    6: 55,
}

# Calendar length: avoid stacking short-plan nudges with raised-band selection.
_MIN_PLAN_WEEKS_FOR_RAISED_PEAK = 18

# Raised peak requires LR ceiling ≥ this (e.g. 50 mpw × 0.40 = 20; 42 × 0.40 = 16.8 → off).
_MIN_VOLUME_CEILING_MILES_FOR_RAISED_PEAK = 19.0

# ``MarathonConfig.max_long_run_share_by_phase["Peak"]`` — max LR share at peak weekly cap.
_MARATHON_PEAK_PHASE_LONG_RUN_SHARE = 0.40

_MARATHON_ABSOLUTE_MAX_TARGET_PEAK_MILES = 20.0


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


def _expected_peak_mpw(
    runs_per_week: Optional[int],
    peak_caps: Optional[Dict[int, int]],
) -> Optional[float]:
    if runs_per_week is None:
        return None
    caps = peak_caps if peak_caps is not None else _DEFAULT_MARATHON_PEAK_CAPS
    v = caps.get(int(runs_per_week))
    if v is None:
        return None
    return float(v)


def resolve_marathon_adaptive_target_peak_miles(
    *,
    weekly_mileage: float,
    primary_goal: Optional[str],
    plan_length_weeks: Optional[int],
    runs_per_week: Optional[int] = None,
    peak_caps: Optional[Dict[int, int]] = None,
    target_time: Optional[str] = None,
    peak_phase_long_run_share: float = _MARATHON_PEAK_PHASE_LONG_RUN_SHARE,
) -> float:
    """
    Marathon peak long run (miles).

    Volume bands (typical target range), driven by effective MPW for band selection:
        mpw < 40  -> 16–18 mi
        40 <= mpw <= 55 -> 18–20 mi
        mpw > 55 -> 20 mi

    **Raised peak:** for Target Time + explicit ``target_time``, sufficient plan length,
    and volume ceiling (``peak_caps[runs_per_week] * peak share``) ≥ 19 mi, band selection
    uses ``max(current_mpw, expected_peak_mpw)`` so low current volume can still target
    a peak LR supported by configured peak-week mileage caps.

    Within a band, \"Just Finish\" biases lower, \"Target Time\" biases higher.
    Short calendars nudge the peak down (floored slightly below the band low when needed).

    When ``runs_per_week`` / caps resolve, the result is clamped to the volume-derived
    ceiling and to 20.0 mi.
    """
    mpw = float(weekly_mileage or 0.0)
    pw = plan_length_weeks

    expected_peak_mpw = _expected_peak_mpw(runs_per_week, peak_caps)
    volume_ceiling_miles: Optional[float] = None
    if expected_peak_mpw is not None and peak_phase_long_run_share > 0:
        volume_ceiling_miles = float(expected_peak_mpw) * float(
            peak_phase_long_run_share
        )

    use_raised_peak = (
        _goal_is_target_time(primary_goal)
        and bool(str(target_time or "").strip())
        and pw is not None
        and int(pw) >= _MIN_PLAN_WEEKS_FOR_RAISED_PEAK
        and volume_ceiling_miles is not None
        and volume_ceiling_miles >= _MIN_VOLUME_CEILING_MILES_FOR_RAISED_PEAK
    )

    mpw_for_bands = mpw
    if use_raised_peak and expected_peak_mpw is not None:
        mpw_for_bands = max(mpw, float(expected_peak_mpw))

    if mpw_for_bands < 40.0:
        lo, hi = 16.0, 18.0
    elif mpw_for_bands <= 55.0:
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

    if volume_ceiling_miles is not None:
        peak = min(peak, volume_ceiling_miles, _MARATHON_ABSOLUTE_MAX_TARGET_PEAK_MILES)

    return float(peak)
