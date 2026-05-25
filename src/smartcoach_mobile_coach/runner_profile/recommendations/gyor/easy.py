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
    GyorBand,
    GyorBandChartZone,
)
from src.smartcoach_mobile_coach.runner_profile.recommendations.gyor.pace_position import (
    _band_for_outside_distance,
    classify_pace_position,
)


def build_easy_gyor_reference(
    *,
    hr_target_z2: HrZoneBand | None,
    goal_aligned_easy_pace: PaceZoneBand | None,
    config: EasyGyorConfig | None = None,
) -> EasyGyorReference | None:
    """Build static easy GYOR reference from marathon goal easy pace + Z2 HR target."""
    if hr_target_z2 is None or goal_aligned_easy_pace is None:
        return None
    cfg = config or DEFAULT_EASY_GYOR_CONFIG
    return EasyGyorReference(
        policy=cfg.fusion.name,
        hr_target_z2=hr_target_z2,
        goal_aligned_easy_pace=goal_aligned_easy_pace,
        pace_zones_chart=build_easy_pace_progress_zones_chart(
            goal_aligned_easy_pace,
            config=cfg,
        ),
    )


def build_easy_pace_progress_zones_chart(
    goal_aligned_easy_pace: PaceZoneBand,
    *,
    config: EasyGyorConfig | None = None,
) -> tuple[GyorBandChartZone, ...]:
    """
    Pace-progress chart bands (HR-free).

    ``min``/``max`` are decimal **minutes/mile** on the chart (lower min/mi = faster).

    Green covers from the chart fast-side cap through the goal-aligned easy corridor
    (**ahead** and **within** range). Faster-than-goal stays green (no punitive
    fast-tier stripes). Slow-side yellow/orange/red use the same offsets as pace
    position config (distance past the corridor's slower edge).
    """
    cfg = config or DEFAULT_EASY_GYOR_CONFIG
    pace_cfg = cfg.pace
    green_lo_sec = float(goal_aligned_easy_pace.low_sec)
    green_hi_sec = float(goal_aligned_easy_pace.high_sec)
    green_lo = green_lo_sec / 60.0
    green_hi = green_hi_sec / 60.0

    y_m = pace_cfg.yellow_outside_sec / 60.0
    o_m = pace_cfg.orange_outside_sec / 60.0
    r_m = pace_cfg.red_outside_sec / 60.0

    cap_fast = max(0.0, green_lo - cfg.chart_fast_axis_cap_min_per_mi)
    cap_slow = green_hi + cfg.chart_slow_axis_cap_min_per_mi

    zones: list[GyorBandChartZone] = [
        {"color": "green", "min": cap_fast, "max": green_hi},
    ]
    tier_edges = [
        ("yellow", green_hi, green_hi + y_m),
        ("orange", green_hi + y_m, green_hi + o_m),
        ("red", green_hi + o_m, green_hi + r_m),
    ]
    for color, lo, hi in tier_edges:
        lo_c = max(lo, green_hi)
        hi_c = min(hi, cap_slow)
        if hi_c > lo_c:
            zones.append({"color": color, "min": lo_c, "max": hi_c})

    last = zones[-1]
    if len(zones) > 1 and last["color"] != "green" and float(last["max"]) < cap_slow:
        zones[-1] = {**last, "max": cap_slow}

    return tuple(zones)


def classify_easy_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    goal_aligned_easy_pace: PaceZoneBand | None,
    config: EasyGyorConfig | None = None,
) -> GyorBand | None:
    """
    Pace vs goal-aligned easy corridor only (**no HR**).

    Faster than or within the corridor → ``green``. Slower tiers use the same
    distance thresholds as :func:`build_easy_pace_progress_zones_chart` (outside
    the slower edge).
    """
    if pace_sec_per_mi is None or goal_aligned_easy_pace is None:
        return None
    cfg_pace = (config or DEFAULT_EASY_GYOR_CONFIG).pace
    try:
        pace = float(pace_sec_per_mi)
    except (TypeError, ValueError):
        return None
    hi = float(goal_aligned_easy_pace.high_sec)
    if pace <= hi:
        return "green"
    return _band_for_outside_distance(pace - hi, config=cfg_pace)


def build_easy_pace_zones_chart(
    goal_aligned_easy_pace: PaceZoneBand,
    *,
    config: EasyGyorConfig | None = None,
) -> tuple[GyorBandChartZone, ...]:
    """
    Y-axis bands for the easy pace chart (min/mi; lower = faster).

    Green corridor matches goal-aligned easy pace; faster/slower regions use
    pace-position thresholds.
    """
    cfg = config or DEFAULT_EASY_GYOR_CONFIG
    pace_cfg = cfg.pace
    green_lo = float(goal_aligned_easy_pace.low_sec) / 60.0
    green_hi = float(goal_aligned_easy_pace.high_sec) / 60.0

    yellow_fast = pace_cfg.yellow_outside_sec / 60.0
    orange_fast = pace_cfg.orange_outside_sec / 60.0
    red_fast = pace_cfg.red_outside_sec / 60.0
    yellow_slow = pace_cfg.yellow_outside_sec / 60.0

    zones: list[GyorBandChartZone] = []

    red_fast_min = max(0.0, green_lo - red_fast)
    orange_fast_min = max(0.0, green_lo - orange_fast)
    yellow_fast_min = max(0.0, green_lo - yellow_fast)

    if red_fast_min < orange_fast_min:
        zones.append({"color": "red", "min": red_fast_min, "max": orange_fast_min})
    if orange_fast_min < yellow_fast_min:
        zones.append(
            {"color": "orange", "min": orange_fast_min, "max": yellow_fast_min}
        )
    if yellow_fast_min < green_lo:
        zones.append({"color": "yellow", "min": yellow_fast_min, "max": green_lo})

    zones.append({"color": "green", "min": green_lo, "max": green_hi})

    slow_yellow_max = green_hi + yellow_slow
    if green_hi < slow_yellow_max:
        zones.append({"color": "yellow", "min": green_hi, "max": slow_yellow_max})

    cap_fast = max(0.0, green_lo - cfg.chart_fast_axis_cap_min_per_mi)
    cap_slow = green_hi + cfg.chart_slow_axis_cap_min_per_mi
    if zones:
        first = zones[0]
        if first["color"] != "green" and float(first["min"]) > cap_fast:
            first = {**first, "min": cap_fast}
            zones[0] = first
        last = zones[-1]
        if last["color"] != "green" and float(last["max"]) < cap_slow:
            last = {**last, "max": cap_slow}
            zones[-1] = last

    return tuple(zones)


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
