"""
Continuous goal-demand score (Wave 4) — marathon time goals mapped to [0, 1].

Faster goals (lower sec/mi) yield higher demand. Used to interpolate pace-alignment
thresholds so small clock changes (e.g. 3:30:00 vs 3:30:01) do not flip regimes.
"""

from __future__ import annotations

from typing import Optional

from src.coaching_intelligence.policy.policy_table import (
    MARATHON_DEMAND_BANDS,
    competitive_marathon_max_seconds,
    marathon_distance_mi,
)


def compute_demand_score(
    target_pace_sec_per_mi: Optional[float],
    race_distance: str,
) -> float:
    """
    Return demand in ``[0, 1]`` for policy interpolation.

    Non-marathon distances and missing/invalid pace return ``0.0``.
    """
    if target_pace_sec_per_mi is None:
        return 0.0
    try:
        pace = float(target_pace_sec_per_mi)
    except (TypeError, ValueError):
        return 0.0
    if pace <= 0:
        return 0.0
    rd = str(race_distance or "").strip().lower()
    if "half" in rd:
        return 0.0
    if "marathon" not in rd:
        return 0.0

    marathon_clock = pace * marathon_distance_mi
    bands = MARATHON_DEMAND_BANDS
    if len(bands) < 2:
        return 0.0
    (t0, d0), (t1, d1) = bands[0], bands[-1]
    if marathon_clock <= t0:
        return float(d0)
    if marathon_clock >= t1:
        return float(d1)
    return float(d0 + (d1 - d0) * (marathon_clock - t0) / (t1 - t0))


def interpolated_pace_gap_thresholds(
    demand_score: float,
    *,
    moderate_easy_warn: float,
    moderate_sustained_warn: float,
    competitive_easy_warn: float,
    competitive_easy_bad: float,
    competitive_sustained_warn: float,
    competitive_sustained_bad: float,
) -> tuple[float, float, float, float]:
    """
    Interpolate (easy_warn, easy_bad, sustained_warn, sustained_bad).

    At demand 0, ``easy_bad`` / ``sustained_bad`` are very large (``O(1/t)`` near 0) so
    BAD rules do not fire. Warn thresholds ease in with ``t⁵`` so moderate marathon goals
    keep sensitivity similar to legacy ``3:30+`` behavior. At demand 1, warn/bad match
    competitive constants.
    """
    t = max(0.0, min(1.0, float(demand_score)))
    tp = t**5
    easy_warn = moderate_easy_warn + tp * (competitive_easy_warn - moderate_easy_warn)
    sustained_warn = moderate_sustained_warn + tp * (
        competitive_sustained_warn - moderate_sustained_warn
    )
    eps = 1e-3
    easy_bad = competitive_easy_bad / max(t, eps)
    sustained_bad = competitive_sustained_bad / max(t, eps)
    return easy_warn, easy_bad, sustained_warn, sustained_bad


def pace_missing_triggers_thin_data(demand_score: float) -> bool:
    """
    Whether missing/low pace reliability should emit ``RULE_PERFORMANCE_PACE_DATA_THIN``.

    Cutoff uses demand at a pace **just past** the legacy 3:30:00 competitive ceiling
    (half-second past), so 3:30:00 vs 3:30:01 do not flip this bit opposite ways.
    """
    p_cut = (float(competitive_marathon_max_seconds) + 0.5) / marathon_distance_mi
    d_cut = compute_demand_score(p_cut, "Marathon")
    return float(demand_score) > d_cut
