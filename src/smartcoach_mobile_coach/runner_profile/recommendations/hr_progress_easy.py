from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand

HrProgressBand = Literal["green", "yellow", "orange", "red"]
HrProgressChartZone = dict[str, float | str]


@dataclass(frozen=True)
class EasyHrProgressReference:
    """Insights Avg HR chart authority (Z2 cap + chart zones)."""

    target_hr_z2: HrZoneBand
    target_display: str
    hr_zones_chart: tuple[HrProgressChartZone, ...]


@dataclass(frozen=True)
class HrProgressEasyConfig:
    """
    Single-cap easy HR for Insights Avg HR chart (mirrors pace_progress).

    Target cap is ``hr_z2.high``. Green = at or below cap; slow-side tiers are
    measured above that cap. Chart axis caps are rendering-only.
    """

    yellow_gap_bpm: float = 3.0
    orange_gap_bpm: float = 7.0
    chart_axis_cap_bpm: float = 18.0


DEFAULT_HR_PROGRESS_EASY_CONFIG = HrProgressEasyConfig()


def target_hr_cap_bpm(hr_z2: HrZoneBand) -> float:
    """Single-target HR cap for Insights Avg HR (``hr_z2.high``)."""
    return float(hr_z2.high)


def format_hr_z2_target_display(band: HrZoneBand) -> str:
    """Cap display for chart footnote / banner (e.g. ``≤143 bpm``)."""
    return f"≤{int(band.high)} bpm"


def format_hr_z2_range_display(band: HrZoneBand) -> str:
    """Full calibrated Z2 range for help copy (e.g. ``120–145 bpm``)."""
    return f"{int(band.low)}–{int(band.high)} bpm"


def build_easy_hr_progress_reference(
    hr_z2: HrZoneBand,
    *,
    config: HrProgressEasyConfig | None = None,
) -> EasyHrProgressReference:
    """Build Z2 cap + chart zones from calibrated profile Z2."""
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

    - **green**: chart low cap → Z2 high cap (at or below target cap)
    - **yellow / orange / red**: progressively higher above Z2 high cap
    """
    cfg = config or DEFAULT_HR_PROGRESS_EASY_CONFIG
    cap = target_hr_cap_bpm(hr_z2)
    y_gap = cfg.yellow_gap_bpm
    o_gap = cfg.orange_gap_bpm

    chart_lo = max(0.0, cap - cfg.chart_axis_cap_bpm)
    chart_hi = cap + o_gap + cfg.chart_axis_cap_bpm

    zones: list[HrProgressChartZone] = []
    zones.append({"color": "green", "min": chart_lo, "max": cap})

    tier_edges = [
        ("yellow", cap, cap + y_gap),
        ("orange", cap + y_gap, cap + o_gap),
        ("red", cap + o_gap, chart_hi),
    ]
    for color, lo, hi in tier_edges:
        lo_c = max(lo, cap)
        hi_c = min(hi, chart_hi)
        if hi_c > lo_c:
            zones.append({"color": color, "min": lo_c, "max": hi_c})

    return tuple(zones)


def classify_easy_hr_progress(
    *,
    avg_hr_bpm: float | None,
    target_hr_z2: HrZoneBand | None,
    config: HrProgressEasyConfig | None = None,
) -> HrProgressBand | None:
    """
    Classify weekly average easy HR vs Z2 high cap only (**HR-only**, no pace).

    Green = at or below cap; yellow/orange/red = progressively above cap.
    Below-Z2-low avg HR is green (not penalized).
    """
    if avg_hr_bpm is None or target_hr_z2 is None:
        return None
    cfg = config or DEFAULT_HR_PROGRESS_EASY_CONFIG
    try:
        hr = float(avg_hr_bpm)
    except (TypeError, ValueError):
        return None

    cap = target_hr_cap_bpm(target_hr_z2)
    if hr <= cap:
        return "green"

    gap = hr - cap
    if gap <= cfg.yellow_gap_bpm:
        return "yellow"
    if gap <= cfg.orange_gap_bpm:
        return "orange"
    return "red"
