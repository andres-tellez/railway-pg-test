from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand

PaceProgressBand = Literal["green", "yellow", "orange", "red"]
PaceProgressChartZone = dict[str, float | str]


@dataclass(frozen=True)
class EasyPaceProgressReference:
    """HR-free pace-progress chart reference (Insights Avg Pace authority)."""

    target_easy_pace: PaceZoneBand
    pace_zones_chart: tuple[PaceProgressChartZone, ...]


@dataclass(frozen=True)
class PaceProgressEasyConfig:
    """
    Single-target easy pace for Insights pace-progress chart (HR-free).

    Target pace comes from ``goal_aligned_easy_pace.low_sec`` (fast edge of goal
    easy band). Slow-side chart tiers are measured past that target.
    Chart axis caps are rendering-only.
    """

    yellow_gap_sec: float = 15.0
    orange_gap_sec: float = 35.0
    chart_fast_axis_cap_min_per_mi: float = 2.0
    chart_slow_axis_cap_min_per_mi: float = 2.0


DEFAULT_PACE_PROGRESS_EASY_CONFIG = PaceProgressEasyConfig()


def _format_target_display(target_sec: int) -> str:
    from src.smartcoach_mobile_coach.display_format import format_pace_sec_per_mi

    return format_pace_sec_per_mi(float(target_sec))


def target_easy_pace_sec(band: PaceZoneBand) -> float:
    """Single-target pace band stores the same value in ``low_sec`` and ``high_sec``."""
    return float(band.low_sec)


def pace_progress_target_from_goal_easy(
    goal_aligned_easy_pace: PaceZoneBand,
) -> PaceZoneBand:
    """
    Derive pace-progress target from the fast edge of the goal easy band.

    Returns a degenerate ``PaceZoneBand`` (``low_sec == high_sec``).
    """
    target_i = int(goal_aligned_easy_pace.low_sec)
    return PaceZoneBand(
        low_sec=target_i,
        high_sec=target_i,
        display=_format_target_display(target_i),
    )


def build_easy_pace_progress_reference(
    goal_aligned_easy_pace: PaceZoneBand,
    *,
    config: PaceProgressEasyConfig | None = None,
) -> EasyPaceProgressReference:
    """Build pace-progress target + chart zones from the goal easy band."""
    pp_cfg = config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    target_easy = pace_progress_target_from_goal_easy(goal_aligned_easy_pace)
    pace_zones = build_easy_pace_progress_zones_chart(target_easy, config=pp_cfg)
    return EasyPaceProgressReference(
        target_easy_pace=target_easy,
        pace_zones_chart=pace_zones,
    )


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


def build_easy_pace_progress_zones_chart(
    target_easy_pace: PaceZoneBand,
    *,
    config: PaceProgressEasyConfig | None = None,
) -> tuple[PaceProgressChartZone, ...]:
    """
    Pace-progress chart bands (HR-free).

    ``min``/``max`` are decimal **minutes/mile** (lower min/mi = faster).

    - **green**: chart fast cap → target easy pace (at or faster than target)
    - **yellow / orange / red**: progressively slower past target easy pace
    """
    cfg = config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    target = target_easy_pace_sec(target_easy_pace) / 60.0

    y_m = cfg.yellow_gap_sec / 60.0
    o_m = cfg.orange_gap_sec / 60.0

    cap_fast = max(0.0, target - cfg.chart_fast_axis_cap_min_per_mi)
    cap_slow = target + o_m + cfg.chart_slow_axis_cap_min_per_mi

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


def classify_easy_pace_progress(
    *,
    pace_sec_per_mi: float | None,
    target_easy_pace: PaceZoneBand | None,
    config: PaceProgressEasyConfig | None = None,
) -> PaceProgressBand | None:
    """
    Pace vs single target easy pace only (**no HR**).

    Green = at or faster than target; slow tiers use configured gaps past target.
    """
    if pace_sec_per_mi is None or target_easy_pace is None:
        return None
    cfg = config or DEFAULT_PACE_PROGRESS_EASY_CONFIG
    try:
        pace = float(pace_sec_per_mi)
    except (TypeError, ValueError):
        return None

    target_sec = target_easy_pace_sec(target_easy_pace)
    if pace <= target_sec:
        return "green"

    gap = pace - target_sec
    if gap <= cfg.yellow_gap_sec:
        return "yellow"
    if gap <= cfg.orange_gap_sec:
        return "orange"
    return "red"
