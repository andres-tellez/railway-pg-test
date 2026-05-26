from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi
from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.models import (
    GoalAlignedPaceBands,
)


@dataclass(frozen=True)
class GoalAlignedPaceConfig:
    """
    Offsets from marathon goal pace (sec/mi) to training pace bands.

    Z3 (Tempo tab): controlled steady/moderate work — MP −15 to +10 sec/mi.
    Z4 (Threshold tab): harder threshold work — MP −40 to −20 sec/mi.
    """

    marathon_distance_mi: float = 26.21876
    easy_min_offset: float = 55.0
    easy_max_offset: float = 85.0
    z3_min_offset: float = -15.0
    z3_max_offset: float = 10.0
    z4_min_offset: float = -40.0
    z4_max_offset: float = -20.0


DEFAULT_GOAL_ALIGNED_PACE_CONFIG = GoalAlignedPaceConfig()


def parse_target_time_to_total_seconds(target_time: str | None) -> Optional[float]:
    """
    Parse target race time string into total seconds.

    Supported forms:
    - HH:MM:SS
    - HH:MM
    """
    if target_time is None:
        return None
    s = str(target_time).strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            sec = float(parts[2])
            return float(h * 3600 + m * 60) + sec
        if len(parts) == 2:
            h = int(parts[0])
            m = int(parts[1])
            return float(h * 3600 + m * 60)
    except (TypeError, ValueError):
        return None
    return None


def _format_band_display(low_sec: int, high_sec: int) -> str:
    lo = format_pace_sec_per_mi(float(low_sec))
    hi = format_pace_sec_per_mi(float(high_sec))
    if low_sec == high_sec or lo == hi:
        return lo
    lo_mmss = lo.removesuffix("/mi") if lo.endswith("/mi") else lo
    hi_mmss = hi.removesuffix("/mi") if hi.endswith("/mi") else hi
    return f"{lo_mmss}–{hi_mmss}/mi"


def _build_band(low_sec: float, high_sec: float) -> PaceZoneBand:
    low_i = int(round(low_sec))
    high_i = int(round(high_sec))
    return PaceZoneBand(
        low_sec=low_i,
        high_sec=high_i,
        display=_format_band_display(low_i, high_i),
    )


def compute_goal_aligned_pace_bands(
    target_time: str | None,
    *,
    config: GoalAlignedPaceConfig = DEFAULT_GOAL_ALIGNED_PACE_CONFIG,
) -> GoalAlignedPaceBands | None:
    """
    Compute goal-aligned training pace bands from marathon target time.
    """
    total_sec = parse_target_time_to_total_seconds(target_time)
    if total_sec is None or config.marathon_distance_mi <= 0.0:
        return None

    marathon_sec = float(total_sec) / float(config.marathon_distance_mi)
    easy = _build_band(
        marathon_sec + config.easy_min_offset,
        marathon_sec + config.easy_max_offset,
    )
    z3 = _build_band(
        marathon_sec + config.z3_min_offset,
        marathon_sec + config.z3_max_offset,
    )
    z4 = _build_band(
        marathon_sec + config.z4_min_offset,
        marathon_sec + config.z4_max_offset,
    )
    marathon = _build_band(marathon_sec, marathon_sec)

    return GoalAlignedPaceBands(
        easy=easy,
        z3=z3,
        z4=z4,
        marathon=marathon,
        marathon_sec=int(round(marathon_sec)),
        source_target_time=str(target_time).strip(),
    )
