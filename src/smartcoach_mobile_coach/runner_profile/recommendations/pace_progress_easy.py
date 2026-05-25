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
    Single-target easy pace for Insights pace-progress chart (HR-free).

    ``target_easy_pace_sec = marathon_pace_sec + easy_target_offset_sec``.
    Slow-side GYOR gaps are measured past that target.
    Chart axis caps are rendering-only.
    """

    marathon_distance_mi: float = 26.21876
    easy_target_offset_sec: float = 55.0
    yellow_gap_sec: float = 15.0
    orange_gap_sec: float = 35.0
    chart_fast_axis_cap_min_per_mi: float = 2.0
    chart_slow_axis_cap_min_per_mi: float = 2.0


DEFAULT_PACE_PROGRESS_EASY_CONFIG = PaceProgressEasyConfig()


def _format_target_display(target_sec: int) -> str:
    from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi

    return format_pace_sec_per_mi(float(target_sec))


def target_easy_pace_sec(band: PaceZoneBand) -> float:
    """Single-target pace band stores the same value in ``low_sec`` and ``high_sec``."""
    return float(band.low_sec)


def compute_pace_progress_target_easy_pace(
    target_time: str | None,
    *,
    config: PaceProgressEasyConfig = DEFAULT_PACE_PROGRESS_EASY_CONFIG,
) -> PaceZoneBand | None:
    """
    Derive pace-progress target easy pace from marathon ``target_time``.

    Returns a degenerate ``PaceZoneBand`` (``low_sec == high_sec``).
    """
    total_sec = _parse_target_time_to_total_seconds(target_time)
    if total_sec is None or config.marathon_distance_mi <= 0.0:
        return None

    marathon_sec = float(total_sec) / float(config.marathon_distance_mi)
    target_i = int(round(marathon_sec + config.easy_target_offset_sec))
    return PaceZoneBand(
        low_sec=target_i,
        high_sec=target_i,
        display=_format_target_display(target_i),
    )
