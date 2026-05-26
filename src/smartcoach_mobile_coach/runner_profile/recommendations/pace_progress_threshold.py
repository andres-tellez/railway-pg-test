from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand

PaceProgressBand = Literal["green", "yellow", "orange", "red"]
PaceProgressChartZone = dict[str, float | str]


@dataclass(frozen=True)
class ThresholdPaceProgressReference:
    """HR-free tempo pace-progress chart reference (Insights Tempo Avg Pace authority)."""

    target_tempo_pace: PaceZoneBand
    target_display: str
    pace_zones_chart: tuple[PaceProgressChartZone, ...]


@dataclass(frozen=True)
class PaceProgressThresholdConfig:
    """
    Goal Z3 corridor for Insights Tempo Avg Pace chart (HR-free).

    Target corridor comes from ``goal_aligned_z3_pace`` (``low_sec`` = fast edge,
    ``high_sec`` = slow edge). Bands outside the corridor use symmetric sec/mi gaps
    on both the fast and slow sides. Chart axis caps are rendering-only.
    """

    yellow_gap_sec: float = 10.0
    orange_gap_sec: float = 25.0
    chart_axis_cap_min_per_mi: float = 2.0


DEFAULT_PACE_PROGRESS_THRESHOLD_CONFIG = PaceProgressThresholdConfig()


def tempo_corridor_sec(goal_aligned_z3_pace: PaceZoneBand) -> tuple[float, float]:
    """Fast and slow edges of the goal tempo corridor (sec/mi; lower = faster)."""
    fast = float(goal_aligned_z3_pace.low_sec)
    slow = float(goal_aligned_z3_pace.high_sec)
    if slow < fast:
        fast, slow = slow, fast
    return fast, slow


def format_tempo_corridor_target_display(band: PaceZoneBand) -> str:
    """Display for banner / chart footnote (reuses goal Z3 band formatting)."""
    return band.display


def build_threshold_pace_progress_reference(
    goal_aligned_z3_pace: PaceZoneBand,
    *,
    config: PaceProgressThresholdConfig | None = None,
) -> ThresholdPaceProgressReference:
    """Build tempo pace-progress corridor + chart zones from goal Z3."""
    cfg = config or DEFAULT_PACE_PROGRESS_THRESHOLD_CONFIG
    zones = build_threshold_pace_progress_zones_chart(goal_aligned_z3_pace, config=cfg)
    return ThresholdPaceProgressReference(
        target_tempo_pace=goal_aligned_z3_pace,
        target_display=format_tempo_corridor_target_display(goal_aligned_z3_pace),
        pace_zones_chart=zones,
    )


def threshold_pace_progress_zones_chart_api_payload(
    zones_chart: tuple[PaceProgressChartZone, ...],
) -> list[dict[str, Any]]:
    """Serialize tempo pace-progress chart zones for REST payloads."""
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


def build_threshold_pace_progress_zones_chart(
    goal_aligned_z3_pace: PaceZoneBand,
    *,
    config: PaceProgressThresholdConfig | None = None,
) -> tuple[PaceProgressChartZone, ...]:
    """
    Tempo pace-progress chart bands (HR-free).

    ``min``/``max`` are decimal **minutes/mile** (lower min/mi = faster).

    - **green**: goal Z3 corridor (fast edge → slow edge)
    - **yellow / orange / red**: symmetric tiers outside the corridor (fast and slow)
    """
    cfg = config or DEFAULT_PACE_PROGRESS_THRESHOLD_CONFIG
    fast_sec, slow_sec = tempo_corridor_sec(goal_aligned_z3_pace)
    fast_m = fast_sec / 60.0
    slow_m = slow_sec / 60.0

    y_m = cfg.yellow_gap_sec / 60.0
    o_m = cfg.orange_gap_sec / 60.0
    cap = cfg.chart_axis_cap_min_per_mi

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


def _band_from_outside_gap(
    gap_sec: float, cfg: PaceProgressThresholdConfig
) -> PaceProgressBand:
    if gap_sec <= cfg.yellow_gap_sec:
        return "yellow"
    if gap_sec <= cfg.orange_gap_sec:
        return "orange"
    return "red"


def classify_threshold_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    goal_aligned_z3_pace: PaceZoneBand | None,
    config: PaceProgressThresholdConfig | None = None,
) -> PaceProgressBand | None:
    """
    Pace vs goal Z3 tempo corridor (**no HR**).

    Green = inside [fast, slow]; yellow/orange/red = outside on either side.
    """
    if pace_sec_per_mi is None or goal_aligned_z3_pace is None:
        return None
    cfg = config or DEFAULT_PACE_PROGRESS_THRESHOLD_CONFIG
    try:
        pace = float(pace_sec_per_mi)
    except (TypeError, ValueError):
        return None

    fast_sec, slow_sec = tempo_corridor_sec(goal_aligned_z3_pace)
    if fast_sec <= pace <= slow_sec:
        return "green"
    if pace > slow_sec:
        return _band_from_outside_gap(pace - slow_sec, cfg)
    return _band_from_outside_gap(fast_sec - pace, cfg)
