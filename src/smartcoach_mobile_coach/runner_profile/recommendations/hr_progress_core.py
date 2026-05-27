from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand

HrProgressBand = Literal["green", "yellow", "orange", "red"]
HrProgressChartZone = dict[str, float | str]


class HrGapTierConfig(Protocol):
    yellow_gap_bpm: float
    orange_gap_bpm: float


@dataclass(frozen=True)
class HrCorridorAxisConfig:
    chart_axis_cap_bpm: float


def hr_progress_zones_chart_api_payload(
    zones_chart: tuple[HrProgressChartZone, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "color": str(zone["color"]),
            "min": float(zone["min"]),
            "max": float(zone["max"]),
        }
        for zone in zones_chart
    ]


def _append_zone(
    zones: list[HrProgressChartZone],
    *,
    color: str,
    lo: float,
    hi: float,
) -> None:
    if hi > lo:
        zones.append({"color": color, "min": lo, "max": hi})


def _band_from_outside_gap(gap_bpm: float, cfg: HrGapTierConfig) -> HrProgressBand:
    if gap_bpm <= cfg.yellow_gap_bpm:
        return "yellow"
    if gap_bpm <= cfg.orange_gap_bpm:
        return "orange"
    return "red"


def hr_corridor_edges_bpm(band: HrZoneBand) -> tuple[float, float]:
    """Low and high edges of an HR corridor (bpm)."""
    lo = float(band.low)
    hi = float(band.high)
    if hi < lo:
        lo, hi = hi, lo
    return lo, hi


def build_hr_corridor_zones_chart(
    corridor: HrZoneBand,
    *,
    gap_cfg: HrGapTierConfig,
    axis_cfg: HrCorridorAxisConfig,
) -> tuple[HrProgressChartZone, ...]:
    """
    HR-progress chart bands in **bpm** (lower on chart = lower HR).

    Green = inside calibrated Z3 corridor; bilateral yellow/orange/red outside.
    """
    z3_lo, z3_hi = hr_corridor_edges_bpm(corridor)
    y_gap = gap_cfg.yellow_gap_bpm
    o_gap = gap_cfg.orange_gap_bpm
    cap = axis_cfg.chart_axis_cap_bpm

    chart_lo = max(0.0, z3_lo - o_gap - cap)
    chart_hi = z3_hi + o_gap + cap

    zones: list[HrProgressChartZone] = []

    _append_zone(zones, color="red", lo=chart_lo, hi=z3_lo - o_gap)
    _append_zone(zones, color="orange", lo=z3_lo - o_gap, hi=z3_lo - y_gap)
    _append_zone(zones, color="yellow", lo=z3_lo - y_gap, hi=z3_lo)
    _append_zone(zones, color="green", lo=z3_lo, hi=z3_hi)
    _append_zone(zones, color="yellow", lo=z3_hi, hi=z3_hi + y_gap)
    _append_zone(zones, color="orange", lo=z3_hi + y_gap, hi=z3_hi + o_gap)
    _append_zone(zones, color="red", lo=z3_hi + o_gap, hi=chart_hi)

    return tuple(zones)


def classify_hr_corridor_progress(
    *,
    avg_hr_bpm: float | None,
    corridor: HrZoneBand | None,
    gap_cfg: HrGapTierConfig,
) -> HrProgressBand | None:
    """Classify HR vs corridor (**HR-only**, no pace). Green = inside [low, high]."""
    if avg_hr_bpm is None or corridor is None:
        return None
    try:
        hr = float(avg_hr_bpm)
    except (TypeError, ValueError):
        return None

    z3_lo, z3_hi = hr_corridor_edges_bpm(corridor)
    if z3_lo <= hr <= z3_hi:
        return "green"
    if hr > z3_hi:
        return _band_from_outside_gap(hr - z3_hi, gap_cfg)
    return _band_from_outside_gap(z3_lo - hr, gap_cfg)
