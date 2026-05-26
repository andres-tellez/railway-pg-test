from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand

PaceProgressBand = Literal["green", "yellow", "orange", "red"]
PaceProgressChartZone = dict[str, float | str]


class GapTierConfig(Protocol):
    yellow_gap_sec: float
    orange_gap_sec: float


@dataclass(frozen=True)
class SingleCapAxisConfig:
    chart_fast_axis_cap_min_per_mi: float
    chart_slow_axis_cap_min_per_mi: float


@dataclass(frozen=True)
class CorridorAxisConfig:
    chart_axis_cap_min_per_mi: float


def pace_progress_zones_chart_api_payload(
    zones_chart: tuple[PaceProgressChartZone, ...],
) -> list[dict[str, Any]]:
    """Serialize pace-progress chart zones for REST payloads."""
    return [
        {
            "color": str(zone["color"]),
            "min": float(zone["min"]),
            "max": float(zone["max"]),
        }
        for zone in zones_chart
    ]


def _append_zone(
    zones: list[PaceProgressChartZone],
    *,
    color: str,
    lo: float,
    hi: float,
) -> None:
    if hi > lo:
        zones.append({"color": color, "min": lo, "max": hi})


def _band_from_outside_gap(gap_sec: float, cfg: GapTierConfig) -> PaceProgressBand:
    if gap_sec <= cfg.yellow_gap_sec:
        return "yellow"
    if gap_sec <= cfg.orange_gap_sec:
        return "orange"
    return "red"


def corridor_edges_sec(band: PaceZoneBand) -> tuple[float, float]:
    """Fast and slow edges of a pace corridor (sec/mi; lower = faster)."""
    fast = float(band.low_sec)
    slow = float(band.high_sec)
    if slow < fast:
        fast, slow = slow, fast
    return fast, slow


def build_single_cap_zones_chart(
    target_sec_per_mi: float,
    *,
    gap_cfg: GapTierConfig,
    axis_cfg: SingleCapAxisConfig,
) -> tuple[PaceProgressChartZone, ...]:
    """
    Pace-progress chart bands for a single target pace (HR-free).

    ``min``/``max`` are decimal **minutes/mile** (lower min/mi = faster).
    """
    target = target_sec_per_mi / 60.0
    y_m = gap_cfg.yellow_gap_sec / 60.0
    o_m = gap_cfg.orange_gap_sec / 60.0

    cap_fast = max(0.0, target - axis_cfg.chart_fast_axis_cap_min_per_mi)
    cap_slow = target + o_m + axis_cfg.chart_slow_axis_cap_min_per_mi

    zones: list[PaceProgressChartZone] = []
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


def build_corridor_zones_chart(
    corridor: PaceZoneBand,
    *,
    gap_cfg: GapTierConfig,
    axis_cfg: CorridorAxisConfig,
) -> tuple[PaceProgressChartZone, ...]:
    """
    Pace-progress chart bands for a goal corridor (HR-free).

    ``min``/``max`` are decimal **minutes/mile** (lower min/mi = faster).
    """
    fast_sec, slow_sec = corridor_edges_sec(corridor)
    fast_m = fast_sec / 60.0
    slow_m = slow_sec / 60.0

    y_m = gap_cfg.yellow_gap_sec / 60.0
    o_m = gap_cfg.orange_gap_sec / 60.0
    cap = axis_cfg.chart_axis_cap_min_per_mi

    cap_fast = max(0.0, fast_m - o_m - cap)
    cap_slow = slow_m + o_m + cap

    zones: list[PaceProgressChartZone] = []

    _append_zone(zones, color="red", lo=cap_fast, hi=fast_m - o_m)
    _append_zone(zones, color="orange", lo=fast_m - o_m, hi=fast_m - y_m)
    _append_zone(zones, color="yellow", lo=fast_m - y_m, hi=fast_m)
    _append_zone(zones, color="green", lo=fast_m, hi=slow_m)
    _append_zone(zones, color="yellow", lo=slow_m, hi=slow_m + y_m)
    _append_zone(zones, color="orange", lo=slow_m + y_m, hi=slow_m + o_m)
    _append_zone(zones, color="red", lo=slow_m + o_m, hi=cap_slow)

    return tuple(zones)


def classify_single_cap_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    target_sec_per_mi: float | None,
    gap_cfg: GapTierConfig,
) -> PaceProgressBand | None:
    """Pace vs single target only (**no HR**)."""
    if pace_sec_per_mi is None or target_sec_per_mi is None:
        return None
    try:
        pace = float(pace_sec_per_mi)
        target_sec = float(target_sec_per_mi)
    except (TypeError, ValueError):
        return None

    if pace <= target_sec:
        return "green"

    gap = pace - target_sec
    return _band_from_outside_gap(gap, gap_cfg)


def classify_corridor_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    corridor: PaceZoneBand | None,
    gap_cfg: GapTierConfig,
) -> PaceProgressBand | None:
    """Pace vs goal corridor (**no HR**). Green = inside [fast, slow]."""
    if pace_sec_per_mi is None or corridor is None:
        return None
    try:
        pace = float(pace_sec_per_mi)
    except (TypeError, ValueError):
        return None

    fast_sec, slow_sec = corridor_edges_sec(corridor)
    if fast_sec <= pace <= slow_sec:
        return "green"
    if pace > slow_sec:
        return _band_from_outside_gap(pace - slow_sec, gap_cfg)
    return _band_from_outside_gap(fast_sec - pace, gap_cfg)
