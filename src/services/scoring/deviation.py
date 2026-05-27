"""
Canonical producer for V1.6 §5 ``deviation_direction`` enum.

PHASE_3_IMPLEMENTATION_CHECKLIST §X.5 single-source-of-truth: this
module is the ONLY place in the codebase that derives
``deviation_direction``. All coach payloads, tools, and routes MUST
call one of the two entry points below — never reimplement the
threshold logic, never mirror it on mobile, and never let the LLM
override it (V1.6 §19: LLM must not derive, override, or contradict
deterministic fields).

Spec reference (SMARTCOACH_SYSTEM_SPEC_V1.md §5)
------------------------------------------------
Three-value enum: ``too_hard`` / ``too_easy`` / ``on_target``.
Omitted (``None``) when any of the following hold:

* HR stream is missing or unusable,
* ``duration_seconds < 600`` (run shorter than 10 minutes),
* ``planned_type`` is Steady (thresholds deferred to V1.7 — spec
  forbids approximation or inheritance).

Per-run-type thresholds (V1, locked — see spec §5 "Per-Run-Type
Thresholds" table)::

    recovery : too_hard >= 5   | too_easy >= 40  | full run
    easy     : too_hard >= 15  | too_easy >= 30  | full run
    tempo    : too_hard >= 20  | too_easy >= 25  | main block only
    long     : too_hard >= 20  | too_easy >= 30  | full run

Tie-breaker (spec §5 rule 1): if both thresholds are exceeded,
resolve to ``too_hard`` ("running too hard is always more costly").

Tempo gap for V1.6
------------------
Tempo deviation MUST be evaluated on the main block only (warm-up
and cool-down excluded). The current codebase stores a single
full-run zone distribution on ``activities.hr_zone_1..5``; there is
no persisted main-block-scoped distribution and no reliable way to
derive one without the raw HR stream + plan-segment boundaries.
Until that infrastructure lands, the activity-level adapter emits
``None`` for every Tempo run — this is strictly correct per spec
("Approximation or inheritance is not permitted — deterministic
correctness is preferred to temporary coverage"), and is documented
in ``PHASE_3_IMPLEMENTATION_CHECKLIST.md`` 3A.5 for a follow-up
pass. Callers that later have main-block metrics can reach the pure
``classify_deviation`` function directly without going through the
activity adapter.

Planned-type vs executed-type zones
-----------------------------------
``deviation_direction`` answers "did the runner execute the PLAN as
intended?" — so ``pct_above`` / ``pct_below`` MUST be measured
against the **planned** run type's target band, not the executed
type's. This differs from ``activities.pct_above_zone`` /
``activities.pct_below_zone`` which are persisted relative to the
``executed_type``. The activity adapter therefore re-derives the
planned-target-relative metrics on the fly.

Target-band vs acceptable-band (deliberate choice)
--------------------------------------------------
Spec §5 wording is "time-above-target" / "time-below-target". The
existing primitive ``zone_metrics_for_type`` measures relative to
the **acceptable** band (bounded by ``acceptable_zone_min`` /
``acceptable_zone_max``) — this is the right semantics for
scoring's zone-compliance bucketing, but the wrong semantics for
deviation direction. Using acceptable bounds would make
``too_easy`` unreachable for Long (``acceptable_zone_min = 1``)
even though the spec assigns it a 30 % threshold.

This module therefore computes ``pct_above_target`` /
``pct_below_target`` directly from ``target_zone_ids`` — the zones
immediately above the max target zone count as above, and the zones
immediately below the min target zone count as below. Note: this
does mean Easy (target = Z1-Z2) and Recovery (target = Z1) have
``pct_below_target == 0`` by construction (there is no zone below
Z1; sub-Z1 HR samples are filtered by ``activity_service`` anyway).
In other words, Easy/Recovery cannot trigger ``too_easy`` via HR
alone, which is a known and accepted characteristic of the V1 HR
model — going "too easy" on an Easy run is not an intensity
failure worth flagging by zone compliance.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from src.services.scoring.zone_compliance import zone_distribution_from_activity
from src.smartcoach_mobile_coach.runner_profile.plan_run_type_registry import (
    RUN_TYPE_DEFINITIONS,
    RUN_TYPE_EASY,
    RUN_TYPE_LONG,
    RUN_TYPE_RECOVERY,
    RUN_TYPE_STEADY,
    RUN_TYPE_TEMPO,
    normalize_run_type_key,
)


class DeviationDirection(str, Enum):
    """V1.6 §5 three-value enum. ``str`` base makes JSON serialization trivial."""

    TOO_HARD = "too_hard"
    TOO_EASY = "too_easy"
    ON_TARGET = "on_target"


# Per-run-type (too_hard_min_pct, too_easy_min_pct) thresholds.
# Keyed by canonical run_type_key (``runner_profile.plan_run_type_registry``).
#
# Intentionally EXCLUDES:
#   * ``steady`` — deferred to V1.7 per spec §5 "Steady TODO"; activity
#     adapter short-circuits to ``None``.
#   * ``tempo`` — listed here so the pure ``classify_deviation`` function
#     can be called with main-block metrics by a future caller once the
#     main-block infrastructure lands. The activity-level adapter in
#     V1.6 still returns ``None`` for tempo (see module docstring).
DEVIATION_THRESHOLDS: dict[str, tuple[float, float]] = {
    RUN_TYPE_RECOVERY: (5.0, 40.0),
    RUN_TYPE_EASY: (15.0, 30.0),
    RUN_TYPE_TEMPO: (20.0, 25.0),
    RUN_TYPE_LONG: (20.0, 30.0),
}

# Spec §5 rule 2: omit when ``duration_seconds < 600`` (10-minute floor).
MIN_DEVIATION_DURATION_SECONDS = 600


def classify_deviation(
    *,
    planned_type_canonical: Optional[str],
    pct_above: Optional[float],
    pct_below: Optional[float],
    duration_seconds: Optional[int],
) -> Optional[DeviationDirection]:
    """
    Pure threshold-classification function. No I/O, no ORM access.

    Inputs are already-normalized canonical values; the caller is
    responsible for:
      * normalizing ``planned_type`` via ``normalize_run_type_key``,
      * supplying ``pct_above`` / ``pct_below`` in the **correct
        scope for the run type** (full-run for recovery/easy/long;
        main-block for tempo — see module docstring).

    Returns ``None`` (omit) when any of:
      * ``planned_type_canonical`` is falsy, unknown, or ``steady``,
      * ``duration_seconds`` is ``None`` or ``< 600``,
      * ``pct_above`` or ``pct_below`` is ``None`` (HR unusable
        /scope-unavailable).

    Tie-breaker: if both thresholds are exceeded, ``too_hard`` wins
    (spec §5 rule 1).

    Args:
        planned_type_canonical: Canonical run-type key. ``steady`` is
            explicitly handled as omit.
        pct_above: Percent-of-time above the planned-type target
            band, scope-appropriate for the run type.
        pct_below: Percent-of-time below the planned-type target
            band, scope-appropriate for the run type.
        duration_seconds: Run duration in seconds (``moving_time``
            on the activity side).

    Returns:
        A :class:`DeviationDirection` enum, or ``None`` for omission.
    """
    if not planned_type_canonical:
        return None
    if planned_type_canonical == RUN_TYPE_STEADY:
        # Spec §5 rule 2: omit for Steady (deferred to V1.7).
        return None
    thresholds = DEVIATION_THRESHOLDS.get(planned_type_canonical)
    if thresholds is None:
        # Unknown / unsupported canonical type — omit rather than guess.
        return None
    if duration_seconds is None or duration_seconds < MIN_DEVIATION_DURATION_SECONDS:
        return None
    if pct_above is None or pct_below is None:
        return None
    too_hard_threshold, too_easy_threshold = thresholds
    above_exceeded = pct_above >= too_hard_threshold
    below_exceeded = pct_below >= too_easy_threshold
    # Tie-breaker (spec §5 rule 1): if both exceeded, too_hard wins.
    # Encoded by checking ``above_exceeded`` first — correctness
    # depends on this ordering; do not rewrite as ``if ... elif`` with
    # different priority.
    if above_exceeded:
        return DeviationDirection.TOO_HARD
    if below_exceeded:
        return DeviationDirection.TOO_EASY
    return DeviationDirection.ON_TARGET


def compute_deviation_direction_for_activity(
    act: Any,
) -> Optional[DeviationDirection]:
    """
    Activity-level adapter — the entry point called by
    ``build_run_execution_block`` and by Phase B plan-aware tools.

    Handles all spec §5 omission rules before dispatching to the
    pure ``classify_deviation`` function, and — critically —
    re-derives the planned-zone-relative ``pct_above`` / ``pct_below``
    from ``hr_zone_1..5`` because ``activity.pct_above_zone`` /
    ``activity.pct_below_zone`` are persisted relative to the
    ``executed_type`` and are the wrong zone-space for deviation
    direction (see module docstring "Planned-type vs executed-type
    zones").

    Tempo V1.6 behavior: returns ``None`` — the required main-block-
    scoped distribution is not yet persisted, and spec §5 rule 3
    forbids full-run approximation. Future main-block work can either
    extend this function or call ``classify_deviation`` directly with
    main-block inputs; the pure function accepts ``tempo`` in
    ``DEVIATION_THRESHOLDS`` so it is ready when that lands.

    Args:
        act: ``Activity`` or duck-typed object exposing
            ``planned_type``, ``moving_time``, and
            ``hr_zone_1..hr_zone_5``.

    Returns:
        :class:`DeviationDirection` or ``None`` per spec §5 omission
        rules.
    """
    planned_type_canonical = normalize_run_type_key(getattr(act, "planned_type", None))
    # Steady omission (explicit to keep the intent obvious even though
    # ``classify_deviation`` would also short-circuit).
    if planned_type_canonical == RUN_TYPE_STEADY:
        return None
    # V1.6 Tempo gap: omit until main-block metrics are available.
    # See module docstring. Phase A item 3 ships spec-compliant
    # behavior for recovery/easy/long; tempo is tracked as a
    # deliberate follow-up (PHASE_3_IMPLEMENTATION_CHECKLIST 3A.5).
    if planned_type_canonical == RUN_TYPE_TEMPO:
        return None
    if planned_type_canonical not in DEVIATION_THRESHOLDS:
        return None

    duration_seconds = getattr(act, "moving_time", None)
    if duration_seconds is None or duration_seconds < MIN_DEVIATION_DURATION_SECONDS:
        return None

    distribution_pct = zone_distribution_from_activity(act)
    if sum(distribution_pct.values()) <= 0:
        # HR missing / unusable (spec §5 rule 2).
        return None

    pct_above, pct_below = _target_band_pct_above_below(
        distribution_pct, planned_type_canonical
    )
    return classify_deviation(
        planned_type_canonical=planned_type_canonical,
        pct_above=pct_above,
        pct_below=pct_below,
        duration_seconds=duration_seconds,
    )


def _target_band_pct_above_below(
    distribution_pct: dict[int, float], run_type_canonical: str
) -> tuple[float, float]:
    """Percent time above / below the **target** zone band.

    See the module docstring ("Target-band vs acceptable-band")
    for why this differs from ``zone_metrics_for_type``. Kept
    private because it is only meaningful in the deviation-
    direction context; scoring continues to use the acceptable-
    band semantics.

    Args:
        distribution_pct: Output of
            :func:`zone_distribution_from_activity` — zone id (1-5)
            → percent of time (0-100).
        run_type_canonical: Canonical run type key (must be present
            in :data:`RUN_TYPE_DEFINITIONS`).

    Returns:
        ``(pct_above_target, pct_below_target)`` rounded to 2 dp.
    """
    definition = RUN_TYPE_DEFINITIONS[run_type_canonical]
    target_min = min(definition.target_zone_ids)
    target_max = max(definition.target_zone_ids)
    pct_above = sum(distribution_pct.get(z, 0.0) for z in range(target_max + 1, 6))
    pct_below = sum(distribution_pct.get(z, 0.0) for z in range(1, target_min))
    return round(pct_above, 2), round(pct_below, 2)
