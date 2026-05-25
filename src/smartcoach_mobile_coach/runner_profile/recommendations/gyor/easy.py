from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand, PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.config import (
    DEFAULT_EASY_GYOR_CONFIG,
    EasyGyorConfig,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.fusion import (
    fuse_gyor_hr_priority,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.hr_position import (
    classify_hr_position,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.models import (
    EasyGyorClassification,
    EasyGyorReference,
    EasyPaceProgressBand,
    GyorBandChartZone,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.pace_position import (
    classify_pace_position,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_easy import (
    DEFAULT_PACE_PROGRESS_EASY_CONFIG,
    PaceProgressEasyConfig,
    compute_pace_progress_target_easy_pace,
    target_easy_pace_sec,
)


def build_easy_gyor_reference(
    *,
    hr_target_z2: HrZoneBand | None,
    goal_aligned_easy_pace: PaceZoneBand | None,
    target_time: str | None = None,
    config: EasyGyorConfig | None = None,
    pace_progress_config: PaceProgressEasyConfig | None = None,
) -> EasyGyorReference | None:
    """Build static easy GYOR reference from marathon goal easy pace + Z2 HR target."""
    if hr_target_z2 is None or goal_aligned_easy_pace is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG
    pp_cfg = pace_progress_config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    target_easy = compute_pace_progress_target_easy_pace(target_time, config=pp_cfg)
    pace_zones = (
        build_easy_pace_progress_zones_chart(target_easy, config=pp_cfg)
        if target_easy is not None
        else ()
    )
    return EasyGyorReference(
        policy=cfg.fusion.name,
        hr_target_z2=hr_target_z2,
        goal_aligned_easy_pace=goal_aligned_easy_pace,
        pace_progress_target_easy_pace=target_easy,
        pace_zones_chart=pace_zones,
    )


def build_easy_pace_progress_zones_chart(
    target_easy_pace: PaceZoneBand,
    *,
    config: PaceProgressEasyConfig | None = None,
) -> tuple[GyorBandChartZone, ...]:
    """
    Pace-progress chart bands (HR-free).

    ``min``/``max`` are decimal **minutes/mile** (lower min/mi = faster).

    - **green**: chart fast cap → target easy pace (at or faster than target)
    - **yellow / orange / red**: progressively slower past target easy pace
    """
    cfg = config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    target = target_easy_pace_sec(target_easy_pace) / 60.0

    y_m = cfg.yellow_gap_sec / 60.0
    o_m = cfg.orange_gap_sec / 60.0

    cap_fast = max(0.0, target - cfg.chart_fast_axis_cap_min_per_mi)
    cap_slow = target + o_m + cfg.chart_slow_axis_cap_min_per_mi

    zones: list[GyorBandChartZone] = []
    zones.append({"color": "green", "min": cap_fast, "max": target})

    tier_edges = [
        ("yellow", target, target + y_m),
        ("orange", target + y_m, target + o_m),
        ("red", target + o_m, cap_slow),
    ]
    for color, lo, hi in tier_edges:
        lo_c = max(lo, target)
        hi_c = min(hi, cap_slow)
        if hi_c > lo_c:
            zones.append({"color": color, "min": lo_c, "max": hi_c})

    return tuple(zones)


def classify_easy_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    target_easy_pace: PaceZoneBand | None,
    config: PaceProgressEasyConfig | None = None,
) -> EasyPaceProgressBand | None:
    """
    Pace vs single target easy pace only (**no HR**).

    Green = at or faster than target; slow tiers use configured gaps past target.
    """
    if pace_sec_per_mi is None or target_easy_pace is None:
        return None
    cfg = config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    try:
        pace = float(pace_sec_per_mi)
    except (TypeError, ValueError):
        return None

    target_sec = target_easy_pace_sec(target_easy_pace)
    if pace <= target_sec:
        return "green"

    gap = pace - target_sec
    if gap <= cfg.yellow_gap_sec:
        return "yellow"
    if gap <= cfg.orange_gap_sec:
        return "orange"
    return "red"


def classify_easy_gyor(
    *,
    pace_sec_per_mi: float | None,
    avg_hr_bpm: float | None,
    reference: EasyGyorReference | None,
    config: EasyGyorConfig | None = None,
) -> EasyGyorClassification | None:
    """Classify one easy week (or session aggregate) against easy GYOR reference."""
    if reference is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG

    band_hr = classify_hr_position(
        avg_hr_bpm,
        hr_target=reference.hr_target_z2,
        config=cfg.hr,
    )
    pace_position = classify_pace_position(
        pace_sec_per_mi,
        goal_aligned_easy_pace=reference.goal_aligned_easy_pace,
        config=cfg.pace,
    )
    band_pace = pace_position.band if pace_position is not None else None
    direction = pace_position.direction if pace_position is not None else None

    band = fuse_gyor_hr_priority(
        band_hr=band_hr,
        pace_position=pace_position,
        policy=cfg.fusion,
    )
    if band is None:
        return None

    return EasyGyorClassification(
        band=band,
        band_hr=band_hr,
        band_pace=band_pace,
        pace_direction=direction,
    )
