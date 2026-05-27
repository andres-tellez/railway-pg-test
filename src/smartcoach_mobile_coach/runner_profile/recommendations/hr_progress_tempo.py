from __future__ import annotations

from dataclasses import dataclass

from src.smartcoach_mobile_coach.runner_profile.models import HrZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.hr_progress_core import (
    HrProgressBand,
    HrProgressChartZone,
    HrCorridorAxisConfig,
    build_hr_corridor_zones_chart,
    classify_hr_corridor_progress,
    hr_corridor_edges_bpm,
    hr_progress_zones_chart_api_payload,
)


@dataclass(frozen=True)
class TempoHrProgressReference:
    """Insights Tempo Avg HR chart authority (calibrated Z3 corridor)."""

    target_hr_z3: HrZoneBand
    target_display: str
    hr_zones_chart: tuple[HrProgressChartZone, ...]


@dataclass(frozen=True)
class HrProgressTempoConfig:
    """
    Calibrated Z3 corridor for Insights Tempo Avg HR chart (pace-free).

    Target corridor comes from ``profile.hr_z3``. Bands outside the corridor
    use symmetric bpm gaps on both the low and high sides.
    """

    yellow_gap_bpm: float = 3.0
    orange_gap_bpm: float = 7.0
    chart_axis_cap_bpm: float = 18.0


DEFAULT_HR_PROGRESS_TEMPO_CONFIG = HrProgressTempoConfig()


def format_hr_z3_target_display(band: HrZoneBand) -> str:
    """Corridor display for chart footnote / banner (e.g. ``155–165 bpm``)."""
    lo, hi = hr_corridor_edges_bpm(band)
    return f"{int(lo)}–{int(hi)} bpm"


def build_tempo_hr_progress_reference(
    hr_z3: HrZoneBand,
    *,
    config: HrProgressTempoConfig | None = None,
) -> TempoHrProgressReference:
    """Build Z3 HR corridor + chart zones from calibrated profile Z3."""
    cfg = config or DEFAULT_HR_PROGRESS_TEMPO_CONFIG
    zones = build_tempo_hr_progress_zones_chart(hr_z3, config=cfg)
    return TempoHrProgressReference(
        target_hr_z3=hr_z3,
        target_display=format_hr_z3_target_display(hr_z3),
        hr_zones_chart=zones,
    )


def tempo_hr_progress_zones_chart_api_payload(
    zones_chart: tuple[HrProgressChartZone, ...],
) -> list[dict[str, object]]:
    return hr_progress_zones_chart_api_payload(zones_chart)


def build_tempo_hr_progress_zones_chart(
    hr_z3: HrZoneBand,
    *,
    config: HrProgressTempoConfig | None = None,
) -> tuple[HrProgressChartZone, ...]:
    cfg = config or DEFAULT_HR_PROGRESS_TEMPO_CONFIG
    return build_hr_corridor_zones_chart(
        hr_z3,
        gap_cfg=cfg,
        axis_cfg=HrCorridorAxisConfig(chart_axis_cap_bpm=cfg.chart_axis_cap_bpm),
    )


def classify_tempo_hr_progress(
    *,
    avg_hr_bpm: float | None,
    target_hr_z3: HrZoneBand | None,
    config: HrProgressTempoConfig | None = None,
) -> HrProgressBand | None:
    """HR vs calibrated Z3 corridor (**no pace**)."""
    cfg = config or DEFAULT_HR_PROGRESS_TEMPO_CONFIG
    return classify_hr_corridor_progress(
        avg_hr_bpm=avg_hr_bpm,
        corridor=target_hr_z3,
        gap_cfg=cfg,
    )
