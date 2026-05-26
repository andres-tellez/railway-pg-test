from __future__ import annotations

from dataclasses import dataclass

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.runner_profile.recommendations.pace_progress_core import (
    CorridorAxisConfig,
    PaceProgressBand,
    PaceProgressChartZone,
    build_corridor_zones_chart,
    classify_corridor_pace_progress,
    corridor_edges_sec,
    pace_progress_zones_chart_api_payload,
)


@dataclass(frozen=True)
class TempoPaceProgressReference:
    """HR-free tempo pace-progress chart reference (Insights Tempo Avg Pace authority)."""

    target_tempo_pace: PaceZoneBand
    target_display: str
    pace_zones_chart: tuple[PaceProgressChartZone, ...]


@dataclass(frozen=True)
class PaceProgressTempoConfig:
    """
    Goal Z3 corridor for Insights Tempo Avg Pace chart (HR-free).

    Target corridor comes from ``goal_aligned_z3_pace``. Bands outside the corridor
    use symmetric sec/mi gaps on both the fast and slow sides.
    """

    yellow_gap_sec: float = 10.0
    orange_gap_sec: float = 25.0
    chart_axis_cap_min_per_mi: float = 2.0


DEFAULT_PACE_PROGRESS_TEMPO_CONFIG = PaceProgressTempoConfig()


def tempo_corridor_sec(goal_aligned_z3_pace: PaceZoneBand) -> tuple[float, float]:
    """Fast and slow edges of the goal tempo corridor (sec/mi; lower = faster)."""
    return corridor_edges_sec(goal_aligned_z3_pace)


def format_tempo_corridor_target_display(band: PaceZoneBand) -> str:
    """Display for banner / chart footnote (reuses goal Z3 band formatting)."""
    return band.display


def build_tempo_pace_progress_reference(
    goal_aligned_z3_pace: PaceZoneBand,
    *,
    config: PaceProgressTempoConfig | None = None,
) -> TempoPaceProgressReference:
    """Build tempo pace-progress corridor + chart zones from goal Z3."""
    cfg = config or DEFAULT_PACE_PROGRESS_TEMPO_CONFIG
    zones = build_tempo_pace_progress_zones_chart(goal_aligned_z3_pace, config=cfg)
    return TempoPaceProgressReference(
        target_tempo_pace=goal_aligned_z3_pace,
        target_display=format_tempo_corridor_target_display(goal_aligned_z3_pace),
        pace_zones_chart=zones,
    )


def tempo_pace_progress_zones_chart_api_payload(
    zones_chart: tuple[PaceProgressChartZone, ...],
) -> list[dict[str, object]]:
    return pace_progress_zones_chart_api_payload(zones_chart)


def build_tempo_pace_progress_zones_chart(
    goal_aligned_z3_pace: PaceZoneBand,
    *,
    config: PaceProgressTempoConfig | None = None,
) -> tuple[PaceProgressChartZone, ...]:
    cfg = config or DEFAULT_PACE_PROGRESS_TEMPO_CONFIG
    return build_corridor_zones_chart(
        goal_aligned_z3_pace,
        gap_cfg=cfg,
        axis_cfg=CorridorAxisConfig(
            chart_axis_cap_min_per_mi=cfg.chart_axis_cap_min_per_mi
        ),
    )


def classify_tempo_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    goal_aligned_z3_pace: PaceZoneBand | None,
    config: PaceProgressTempoConfig | None = None,
) -> PaceProgressBand | None:
    """Pace vs goal Z3 tempo corridor (**no HR**)."""
    cfg = config or DEFAULT_PACE_PROGRESS_TEMPO_CONFIG
    return classify_corridor_pace_progress(
        pace_sec_per_mi=pace_sec_per_mi,
        corridor=goal_aligned_z3_pace,
        gap_cfg=cfg,
    )
