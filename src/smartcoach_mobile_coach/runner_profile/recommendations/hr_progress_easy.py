from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand

HrProgressBand = Literal["green", "yellow", "orange", "red"]
HrProgressChartZone = dict[str, float | str]


@dataclass(frozen=True)
class EasyHrProgressReference:
    """Insights Avg HR chart authority (Z2 target + chart zones)."""

    target_hr_z2: HrZoneBand
    target_display: str
    hr_zones_chart: tuple[HrProgressChartZone, ...]


@dataclass(frozen=True)
class HrProgressEasyConfig:
    """
    Z2 envelope for Insights Avg HR chart.

    Green = inside calibrated Z2. Yellow / orange / red = progressively
    farther outside Z2 (symmetric above high and below low).
    Chart axis caps are rendering-only.
    """

    yellow_gap_bpm: float = 5.0
    orange_gap_bpm: float = 12.0
    chart_axis_cap_bpm: float = 18.0


DEFAULT_HR_PROGRESS_EASY_CONFIG = HrProgressEasyConfig()


def format_hr_z2_target_display(band: HrZoneBand) -> str:
    return f"{int(band.low)}–{int(band.high)} bpm"


def build_easy_hr_progress_reference(
    hr_z2: HrZoneBand,
    *,
    config: HrProgressEasyConfig | None = None,
) -> EasyHrProgressReference:
    """Build Z2 target + chart zones from calibrated profile Z2."""
    cfg = config or DEFAULT_HR_PROGRESS_EASY_CONFIG
    zones = build_easy_hr_progress_zones_chart(hr_z2, config=cfg)
    return EasyHrProgressReference(
        target_hr_z2=hr_z2,
        target_display=format_hr_z2_target_display(hr_z2),
        hr_zones_chart=zones,
    )


def hr_progress_zones_chart_api_payload(
    zones_chart: tuple[HrProgressChartZone, ...],
) -> list[dict[str, Any]]:
    """Serialize hr-progress chart zones for REST payloads."""
    return [
        {
            "color": str(zone["color"]),
            "min": float(zone["min"]),
            "max": float(zone["max"]),
        }
        for zone in zones_chart
    ]


def build_easy_hr_progress_zones_chart(
    hr_z2: HrZoneBand,
    *,
    config: HrProgressEasyConfig | None = None,
) -> tuple[HrProgressChartZone, ...]:
    """
    HR-progress chart bands in **bpm** (lower on chart = lower HR).

    - **green**: Z2 low → Z2 high (in easy HR envelope)
    - **yellow / orange / red**: progressively outside Z2
    """
    cfg = config or DEFAULT_HR_PROGRESS_EASY_CONFIG
    z_lo = float(hr_z2.low)
    z_hi = float(hr_z2.high)
    y_gap = cfg.yellow_gap_bpm
    o_gap = cfg.orange_gap_bpm
    cap = cfg.chart_axis_cap_bpm

    axis_lo = max(0.0, z_lo - o_gap - cap)
    axis_hi = z_hi + o_gap + cap

    zones: list[HrProgressChartZone] = []
    zones.append({"color": "green", "min": z_lo, "max": z_hi})

    tier_specs: list[tuple[str, float, float]] = [
        ("yellow", z_lo - y_gap, z_lo),
        ("yellow", z_hi, z_hi + y_gap),
        ("orange", z_lo - o_gap, z_lo - y_gap),
        ("orange", z_hi + y_gap, z_hi + o_gap),
        ("red", axis_lo, z_lo - o_gap),
        ("red", z_hi + o_gap, axis_hi),
    ]
    for color, lo, hi in tier_specs:
        lo_c = max(lo, axis_lo)
        hi_c = min(hi, axis_hi)
        if hi_c > lo_c:
            zones.append({"color": color, "min": lo_c, "max": hi_c})

    return tuple(zones)


def classify_easy_hr_progress(
    *,
    avg_hr_bpm: float | None,
    target_hr_z2: HrZoneBand | None,
    config: HrProgressEasyConfig | None = None,
) -> HrProgressBand | None:
    """Classify weekly average easy HR vs calibrated Z2 envelope."""
    if avg_hr_bpm is None or target_hr_z2 is None:
        return None
    cfg = config or DEFAULT_HR_PROGRESS_EASY_CONFIG
    try:
        hr = float(avg_hr_bpm)
    except (TypeError, ValueError):
        return None

    z_lo = float(target_hr_z2.low)
    z_hi = float(target_hr_z2.high)
    if z_lo <= hr <= z_hi:
        return "green"

    gap = (hr - z_hi) if hr > z_hi else (z_lo - hr)
    if gap <= cfg.yellow_gap_bpm:
        return "yellow"
    if gap <= cfg.orange_gap_bpm:
        return "orange"
    return "red"
