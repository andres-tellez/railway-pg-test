"""
Zone-compliance primitives — single source of truth for
(in_target, pct_above, pct_below) derivation from HR zone distributions.

Spec references
---------------
- `SMARTCOACH_SYSTEM_SPEC_V1.md` §5 — Tolerance System and the
  V1.6 `deviation_direction` thresholds that read `pct_above_zone` /
  `pct_below_zone` directly.
- `PHASE_3_IMPLEMENTATION_CHECKLIST.md` 0.3 and §X.5 — single-source-of-truth
  rule: every deterministic field has exactly one producer function.

What lives here
---------------
- `zone_distribution_from_activity(activity)` — turn `hr_zone_1..hr_zone_5`
  (seconds) into a percentage-of-time distribution dict.
- `zone_metrics_for_type(distribution_pct, run_type_key)` — collapse the
  5-zone distribution into `(in_target, pct_above, pct_below)` for a given
  run type, using `RunTypeDefinition.target_zone_ids` and
  `acceptable_zone_min` / `acceptable_zone_max` as the only source of what
  "in target / above / below" means per run type.

What does NOT live here
-----------------------
- Per-zone *time accumulation* from raw HR samples. That is upstream and
  lives in `src.services.activity_service`. This module consumes the
  already-accumulated `hr_zone_1..hr_zone_5` columns on `Activity`.
- Scoring / bucketing (green/yellow/red) and plan-alignment penalties.
  Those live in `src.services.run_execution_analysis_service` and will move
  into their own modules if further refactoring is warranted.
- V1.6 `deviation_direction` enum derivation. That is a separate producer
  (see §X.5 row `deviation_direction`) which will consume this module's
  outputs.

Design notes
------------
Callers in V1.6 Phase A (deviation module) must never re-derive pct_above
or pct_below from `hr_zone_*` columns directly — doing so would duplicate
the "what counts as above/below this run type's acceptable band" rule that
is centralized here via `RunTypeDefinition`.
"""

from __future__ import annotations

from typing import NamedTuple, Protocol

from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_DEFINITIONS,
)


class _ActivityZoneReader(Protocol):
    """Minimal structural contract for the Activity inputs we need.

    Declared here so callers can pass a mock/dict-like object in tests
    without importing the full ORM model.
    """

    hr_zone_1: float | int | None
    hr_zone_2: float | int | None
    hr_zone_3: float | int | None
    hr_zone_4: float | int | None
    hr_zone_5: float | int | None


class ZoneMetrics(NamedTuple):
    """Tuple of per-run-type zone compliance metrics.

    Preserves positional unpacking (``in_target, above, below = ...``) for
    backward compatibility with existing call sites, while also offering
    named access (``metrics.pct_above``) for new V1.6 callers.

    All three values are in percentage points (0–100), rounded to two
    decimal places, and sum to ~100 when the input distribution does.
    """

    in_target: float
    pct_above: float
    pct_below: float


def zone_distribution_from_activity(
    activity: _ActivityZoneReader,
) -> dict[int, float]:
    """Return ``{zone_id: percent_of_time_in_zone}`` for zones 1–5.

    Each zone value is read from ``hr_zone_1..hr_zone_5`` (seconds or
    percentages, treated as relative weights). If the sum is non-positive
    the raw values are returned unchanged — callers treat that as "no HR
    data" and skip downstream scoring (see
    `run_execution_analysis_service.analyze_activity_execution`).

    Args:
        activity: Object exposing ``hr_zone_1..hr_zone_5`` attributes.
            Any ``None`` value is coerced to ``0.0``.

    Returns:
        Dict mapping zone id (int, 1–5) to percent of time in zone (float).
        When total is zero, returns the zeros dict as-is.
    """
    zones = {
        1: float(activity.hr_zone_1 or 0.0),
        2: float(activity.hr_zone_2 or 0.0),
        3: float(activity.hr_zone_3 or 0.0),
        4: float(activity.hr_zone_4 or 0.0),
        5: float(activity.hr_zone_5 or 0.0),
    }
    total = sum(zones.values())
    if total <= 0:
        return zones
    return {zone_id: (value / total) * 100.0 for zone_id, value in zones.items()}


def zone_metrics_for_type(
    distribution_pct: dict[int, float], run_type_key: str
) -> ZoneMetrics:
    """Collapse a 5-zone distribution into (in_target, pct_above, pct_below).

    Uses the canonical ``RunTypeDefinition`` for the given run type:
      - ``in_target``  = sum over ``target_zone_ids``
      - ``pct_below``  = sum over zones below ``acceptable_zone_min``
      - ``pct_above``  = sum over zones above ``acceptable_zone_max``

    Values outside the acceptable band are counted as above/below; values
    strictly inside the acceptable band but outside the target band are
    counted as neither (they are "acceptable but not ideal"). This matches
    the long-standing V1 behavior of ``_zone_metrics_for_type`` and is
    depended on by V1.6 `deviation_direction` thresholds (§5).

    Args:
        distribution_pct: Output of :func:`zone_distribution_from_activity`
            (or any dict shaped the same way — zone ids 1–5 mapping to
            percent-of-time floats).
        run_type_key: Canonical run type key from
            :data:`src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry.RUN_TYPE_DEFINITIONS`.

    Returns:
        :class:`ZoneMetrics` with three floats, each rounded to two
        decimal places.

    Raises:
        KeyError: if ``run_type_key`` is not a canonical run type.
    """
    definition = RUN_TYPE_DEFINITIONS[run_type_key]
    in_target = sum(distribution_pct.get(z, 0.0) for z in definition.target_zone_ids)
    pct_below = sum(
        distribution_pct.get(z, 0.0) for z in range(1, definition.acceptable_zone_min)
    )
    pct_above = sum(
        distribution_pct.get(z, 0.0)
        for z in range(definition.acceptable_zone_max + 1, 6)
    )
    return ZoneMetrics(
        in_target=round(in_target, 2),
        pct_above=round(pct_above, 2),
        pct_below=round(pct_below, 2),
    )
