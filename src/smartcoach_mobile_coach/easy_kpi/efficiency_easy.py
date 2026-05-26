from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.smartcoach_mobile_coach.easy_kpi._zones import kpi_zones_chart_api_payload

EfficiencyBand = Literal["green", "yellow", "orange", "red"]
EfficiencyChartZone = dict[str, float | str]

EFFICIENCY_GOAL_DISPLAY = "higher is better at the same effort"


@dataclass(frozen=True)
class EfficiencyBandConfig:
    """Aerobic efficiency scalar thresholds (Insights Efficiency chart authority)."""

    orange_min: float = 3.9
    yellow_min: float = 4.3
    green_min: float = 4.7
    chart_green_axis_cap: float = 0.8


DEFAULT_EFFICIENCY_BAND_CONFIG = EfficiencyBandConfig()


@dataclass(frozen=True)
class EasyEfficiencyReference:
    """Insights Efficiency chart authority (global bands v1)."""

    goal_display: str
    efficiency_zones_chart: tuple[EfficiencyChartZone, ...]


def default_efficiency_band_config() -> EfficiencyBandConfig:
    return DEFAULT_EFFICIENCY_BAND_CONFIG


def format_efficiency_goal_display() -> str:
    """Footnote body for Efficiency chart (prefix with ``Goal:`` on client)."""
    return EFFICIENCY_GOAL_DISPLAY


def build_easy_efficiency_zones_chart(
    config: EfficiencyBandConfig | None = None,
) -> tuple[EfficiencyChartZone, ...]:
    """Efficiency chart bands — semantics match ``classify_easy_efficiency``."""
    cfg = config or DEFAULT_EFFICIENCY_BAND_CONFIG
    o_lo = cfg.orange_min
    y_lo = cfg.yellow_min
    g_lo = cfg.green_min
    g_cap = round(g_lo + cfg.chart_green_axis_cap, 1)
    return (
        {"color": "red", "min": 0.0, "max": o_lo},
        {"color": "orange", "min": o_lo, "max": y_lo},
        {"color": "yellow", "min": y_lo, "max": g_lo},
        {"color": "green", "min": g_lo, "max": g_cap},
    )


def build_easy_efficiency_reference(
    config: EfficiencyBandConfig | None = None,
) -> EasyEfficiencyReference:
    cfg = config or DEFAULT_EFFICIENCY_BAND_CONFIG
    return EasyEfficiencyReference(
        goal_display=format_efficiency_goal_display(),
        efficiency_zones_chart=build_easy_efficiency_zones_chart(cfg),
    )


def efficiency_zones_chart_api_payload(
    zones_chart: tuple[EfficiencyChartZone, ...],
) -> list[dict[str, float | str]]:
    return kpi_zones_chart_api_payload(zones_chart)


def classify_easy_efficiency(
    *,
    efficiency: float | None,
    config: EfficiencyBandConfig | None = None,
) -> EfficiencyBand | None:
    """Map weekly aerobic efficiency scalar to Insights band (higher = better)."""
    if efficiency is None:
        return None
    cfg = config or DEFAULT_EFFICIENCY_BAND_CONFIG
    try:
        v = float(efficiency)
    except (TypeError, ValueError):
        return None
    if v >= cfg.green_min:
        return "green"
    if v >= cfg.yellow_min:
        return "yellow"
    if v >= cfg.orange_min:
        return "orange"
    return "red"
