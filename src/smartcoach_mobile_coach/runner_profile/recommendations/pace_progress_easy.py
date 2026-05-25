from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand


def _parse_target_time_to_total_seconds(target_time: str | None) -> Optional[float]:
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


@dataclass(frozen=True)
class PaceProgressEasyConfig:
    """
    Tighter easy corridor for Insights pace-progress chart vs broad goal envelope.

    Offsets are seconds/mi above marathon goal pace (same anchor as goal-aligned bands).
    Slow-side GYOR gaps are measured past ``pace_progress_easy_slow_offset_sec``.
    """

    marathon_distance_mi: float = 26.21876
    pace_progress_easy_fast_offset_sec: float = 45.0
    pace_progress_easy_slow_offset_sec: float = 75.0
    yellow_slow_gap_sec: float = 15.0
    orange_slow_gap_sec: float = 35.0
    chart_fast_axis_cap_min_per_mi: float = 2.0
    chart_slow_axis_cap_min_per_mi: float = 2.0


DEFAULT_PACE_PROGRESS_EASY_CONFIG = PaceProgressEasyConfig()


def _format_band_display(low_sec: int, high_sec: int) -> str:
    from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi

    lo = format_pace_sec_per_mi(float(low_sec))
    hi = format_pace_sec_per_mi(float(high_sec))
    if low_sec == high_sec or lo == hi:
        return lo
    lo_mmss = lo.removesuffix("/mi") if lo.endswith("/mi") else lo
    hi_mmss = hi.removesuffix("/mi") if hi.endswith("/mi") else hi
    return f"{lo_mmss}–{hi_mmss}/mi"


def _build_corridor_band(low_sec: float, high_sec: float) -> PaceZoneBand:
    low_i = int(round(low_sec))
    high_i = int(round(high_sec))
    return PaceZoneBand(
        low_sec=low_i,
        high_sec=high_i,
        display=_format_band_display(low_i, high_i),
    )


def compute_pace_progress_easy_corridor(
    target_time: str | None,
    *,
    config: PaceProgressEasyConfig = DEFAULT_PACE_PROGRESS_EASY_CONFIG,
) -> PaceZoneBand | None:
    """
    Derive pace-progress target corridor from marathon ``target_time``.

    ``low_sec`` = faster edge; ``high_sec`` = slower edge (sec/mi).
    """
    total_sec = _parse_target_time_to_total_seconds(target_time)
    if total_sec is None or config.marathon_distance_mi <= 0.0:
        return None

    marathon_sec = float(total_sec) / float(config.marathon_distance_mi)
    return _build_corridor_band(
        marathon_sec + config.pace_progress_easy_fast_offset_sec,
        marathon_sec + config.pace_progress_easy_slow_offset_sec,
    )
