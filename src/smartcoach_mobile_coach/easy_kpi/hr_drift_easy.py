from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.smartcoach_mobile_coach.easy_kpi._zones import kpi_zones_chart_api_payload

HrDriftBand = Literal["green", "yellow", "orange", "red"]
HrDriftChartZone = dict[str, float | str]


@dataclass(frozen=True)
class HrDriftBandConfig:
    """HR drift % thresholds (Insights HR Drift chart authority)."""

    green_max: float = 2.5
    yellow_max: float = 5.0
    orange_max: float = 7.5
    chart_red_axis_cap: float = 2.5


DEFAULT_HR_DRIFT_BAND_CONFIG = HrDriftBandConfig()


@dataclass(frozen=True)
class EasyHrDriftReference:
    """Insights HR Drift chart authority (global app-wide KPI bands)."""

    target_display: str
    drift_zones_chart: tuple[HrDriftChartZone, ...]


def default_hr_drift_band_config() -> HrDriftBandConfig:
    return DEFAULT_HR_DRIFT_BAND_CONFIG


def _format_drift_pct(value: float) -> str:
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return str(rounded)


def format_hr_drift_target_display(config: HrDriftBandConfig | None = None) -> str:
    """Footnote body for HR Drift chart (prefix with ``Target drift:`` on client)."""
    cfg = config or DEFAULT_HR_DRIFT_BAND_CONFIG
    g = _format_drift_pct(cfg.green_max)
    y = _format_drift_pct(cfg.yellow_max)
    return f"under {g}% ideal, under {y}% acceptable"


def build_easy_hr_drift_zones_chart(
    config: HrDriftBandConfig | None = None,
) -> tuple[HrDriftChartZone, ...]:
    """HR drift % chart bands — semantics match ``classify_easy_hr_drift``."""
    cfg = config or DEFAULT_HR_DRIFT_BAND_CONFIG
    g_max = cfg.green_max
    y_max = cfg.yellow_max
    o_max = cfg.orange_max
    red_cap = round(o_max + cfg.chart_red_axis_cap, 1)
    return (
        {"color": "green", "min": 0.0, "max": g_max},
        {"color": "yellow", "min": g_max, "max": y_max},
        {"color": "orange", "min": y_max, "max": o_max},
        {"color": "red", "min": o_max, "max": red_cap},
    )


def build_easy_hr_drift_reference(
    config: HrDriftBandConfig | None = None,
) -> EasyHrDriftReference:
    cfg = config or DEFAULT_HR_DRIFT_BAND_CONFIG
    return EasyHrDriftReference(
        target_display=format_hr_drift_target_display(cfg),
        drift_zones_chart=build_easy_hr_drift_zones_chart(cfg),
    )


def hr_drift_zones_chart_api_payload(
    zones_chart: tuple[HrDriftChartZone, ...],
) -> list[dict[str, float | str]]:
    return kpi_zones_chart_api_payload(zones_chart)


def classify_easy_hr_drift(
    *,
    drift_pct: float | None,
    config: HrDriftBandConfig | None = None,
) -> HrDriftBand | None:
    """Map weekly or per-run HR drift % to Insights band (lower drift = better)."""
    if drift_pct is None:
        return None
    cfg = config or DEFAULT_HR_DRIFT_BAND_CONFIG
    try:
        v = float(drift_pct)
    except (TypeError, ValueError):
        return None
    if v < cfg.green_max:
        return "green"
    if v < cfg.yellow_max:
        return "yellow"
    if v < cfg.orange_max:
        return "orange"
    return "red"
