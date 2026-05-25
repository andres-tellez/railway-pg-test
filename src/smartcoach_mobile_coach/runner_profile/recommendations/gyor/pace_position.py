from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.config import (
    DEFAULT_EASY_GYOR_CONFIG,
    GyorPacePositionConfig,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    GyorBand,
    GyorPaceDirection,
    GyorPacePosition,
)


def _band_for_outside_distance(
    distance_sec: float,
    *,
    config: GyorPacePositionConfig,
    cap: GyorBand | None = None,
) -> GyorBand:
    if distance_sec <= config.yellow_outside_sec:
        band: GyorBand = "yellow"
    elif distance_sec <= config.orange_outside_sec:
        band = "orange"
    else:
        band = "red"
    if cap is not None:
        order = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
        if order[band] > order[cap]:
            return cap
    return band


def classify_pace_position(
    pace_sec_per_mi: float | None,
    *,
    goal_aligned_easy_pace: PaceZoneBand | None,
    config: GyorPacePositionConfig | None = None,
) -> GyorPacePosition | None:
    """
    Map pace (sec/mi) to GYOR band and direction vs goal-aligned easy corridor.

    Too-slow easy pace is capped at yellow (never orange/red).
    """
    if pace_sec_per_mi is None or goal_aligned_easy_pace is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG.pace
    try:
        pace = float(pace_sec_per_mi)
    except (TypeError, ValueError):
        return None

    low = float(goal_aligned_easy_pace.low_sec)
    high = float(goal_aligned_easy_pace.high_sec)
    if low <= pace <= high:
        return GyorPacePosition(band="green", direction="inside")

    if pace < low:
        distance = low - pace
        return GyorPacePosition(
            band=_band_for_outside_distance(distance, config=cfg),
            direction="fast",
        )

    distance = pace - high
    slow_cap: GyorBand = "yellow"
    if cfg.max_band_when_too_slow in ("green", "yellow", "orange", "red"):
        slow_cap = cfg.max_band_when_too_slow  # type: ignore[assignment]
    return GyorPacePosition(
        band=_band_for_outside_distance(distance, config=cfg, cap=slow_cap),
        direction="slow",
    )
