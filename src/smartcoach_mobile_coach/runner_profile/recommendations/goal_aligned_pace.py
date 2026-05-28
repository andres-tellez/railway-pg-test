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

GOAL_ALIGNED_STATUS_ACTIVE = "active"
GOAL_ALIGNED_STATUS_MISSING_TARGET_TIME = "missing_target_time"
GOAL_ALIGNED_STATUS_UNSUPPORTED_RACE = "unsupported_race"
GOAL_ALIGNED_STATUS_UNAVAILABLE = "unavailable"


def resolve_goal_aligned_config(
    race_distance: str | None,
) -> GoalAlignedPaceConfig | None:
    """
    Map plan race distance to goal-aligned pace config.

    Marathon (and missing/blank distance for backward compatibility) uses the
    existing marathon offsets. Half marathon and other distances return ``None``
    until a dedicated config is added — add a branch here, not in consumers.
    """
    if race_distance is None or not str(race_distance).strip():
        return DEFAULT_GOAL_ALIGNED_PACE_CONFIG

    from src.services.training_plan.v2.race_distance_factory_v2 import (
        normalize_race_distance,
    )

    normalized = normalize_race_distance(str(race_distance))
    if normalized == "Marathon":
        return DEFAULT_GOAL_ALIGNED_PACE_CONFIG
    return None


def resolve_goal_aligned_status(
    *,
    race_distance: str | None,
    target_time: str | None,
    has_goal_bands: bool,
) -> str:
    """Explain why goal-aligned Insights pace bands are or are not present."""
    if resolve_goal_aligned_config(race_distance) is None:
        return GOAL_ALIGNED_STATUS_UNSUPPORTED_RACE
    if parse_target_time_to_total_seconds(target_time) is None:
        return GOAL_ALIGNED_STATUS_MISSING_TARGET_TIME
    if has_goal_bands:
        return GOAL_ALIGNED_STATUS_ACTIVE
    return GOAL_ALIGNED_STATUS_UNAVAILABLE


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
    race_distance: str | None = None,
    config: GoalAlignedPaceConfig | None = None,
) -> GoalAlignedPaceBands | None:
    """
    Compute goal-aligned training pace bands from plan target time.

    ``race_distance`` selects the config via ``resolve_goal_aligned_config``;
    only marathon math is implemented today.
    """
    resolved_config = (
        config if config is not None else resolve_goal_aligned_config(race_distance)
    )
    if resolved_config is None:
        return None

    total_sec = parse_target_time_to_total_seconds(target_time)
    if total_sec is None or resolved_config.marathon_distance_mi <= 0.0:
        return None

    marathon_sec = float(total_sec) / float(resolved_config.marathon_distance_mi)
    easy = _build_band(
        marathon_sec + resolved_config.easy_min_offset,
        marathon_sec + resolved_config.easy_max_offset,
    )
    z3 = _build_band(
        marathon_sec + resolved_config.z3_min_offset,
        marathon_sec + resolved_config.z3_max_offset,
    )
    z4 = _build_band(
        marathon_sec + resolved_config.z4_min_offset,
        marathon_sec + resolved_config.z4_max_offset,
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
