from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.config import (
    DEFAULT_EASY_GYOR_CONFIG,
    EasyGyorConfig,
    GyorHrPositionConfig,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    GyorBand,
)


def classify_hr_position(
    avg_hr_bpm: float | None,
    *,
    hr_target: HrZoneBand | None,
    config: GyorHrPositionConfig | None = None,
) -> GyorBand | None:
    """
    Map average HR to GYOR band relative to the target easy HR range.
    """
    if avg_hr_bpm is None or hr_target is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG.hr
    try:
        hr = float(avg_hr_bpm)
    except (TypeError, ValueError):
        return None

    low = float(hr_target.low)
    high = float(hr_target.high)
    if low <= hr <= high:
        return "green"
    if hr > high:
        above = hr - high
        if above <= cfg.yellow_above_high_bpm:
            return "yellow"
        if above <= cfg.orange_above_high_bpm:
            return "orange"
        return "red"
    below = low - hr
    if below <= cfg.yellow_below_low_bpm:
        return "yellow"
    return "yellow"
