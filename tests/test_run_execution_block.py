"""
Tests for the V1.6 Pre-Phase A 0.A canonical run-execution block.

Locks in:

1. ``build_run_execution_block`` produces the V1.6 namespaced
   ``planned.* / actual.*`` shape from the canonical ``Activity`` fields.
2. ``execution_block_to_weekly_plan_shape`` is byte-exact parity with
   the deleted ``plan_routes._execution_payload`` shape (consumed by
   mobile ``CurrentWeekExecutionPayload``).
3. ``execution_block_to_insight_summary_shape`` is byte-exact parity
   with the pre-0.A ``facts.execution_summary`` dict literal in
   ``build_get_run_insight_payload``.

The parity tests are the single-source-of-truth enforcement: if any
future change drifts the extracted fields between ``get_run_summary``
and ``GET /api/plan/current-week``, these tests fail first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from src.smartcoach_mobile_coach.run_insight import (
    build_run_execution_block,
    execution_block_to_insight_summary_shape,
    execution_block_to_weekly_plan_shape,
)


@dataclass
class _FakeActivity:
    """Minimal stand-in for src.db.models.activities.Activity."""

    activity_id: int = 12345
    start_date: Any = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    matched_plan_workout_id: Any = 777
    planned_type: Any = "easy"
    executed_type: Any = "easy"
    run_score: Any = "green"
    zone_compliance_pct: Any = 82.5
    pct_above_zone: Any = 7.0
    pct_below_zone: Any = 10.5
    planned_miles: Any = 5.0
    actual_miles: Any = 5.1
    completion_pct: Any = 1.02
    scoring_detail: Any = None
    average_heartrate: Any = 138.4
    conv_distance: Any = 5.1
    moving_time: Any = 2754
    # HR zone time (seconds-like weights) — required for V1.6 Phase A
    # item 3 deviation_direction derivation. Default distribution
    # lands this Easy-planned run ON_TARGET: 100% in-target (Z2) →
    # pct_above_target = 0, pct_below_target = 0 (sub-Z1 impossible).
    hr_zone_1: Any = 0
    hr_zone_2: Any = 2754
    hr_zone_3: Any = 0
    hr_zone_4: Any = 0
    hr_zone_5: Any = 0


def test_build_run_execution_block_namespaced_shape():
    """
    V1.6 §6 contract: planned.* and actual.* are strictly separated.
    ``matched_plan_workout_id`` and ``plan_status`` are pairing
    metadata and live outside the namespaces.
    """
    block = build_run_execution_block(_FakeActivity())
    assert set(block.keys()) == {
        "matched_plan_workout_id",
        "plan_status",
        "violated_rest_day",
        "planned",
        "actual",
    }
    assert block["matched_plan_workout_id"] == 777
    # V1.6 §6 + Phase A item 1: linked activity → "executed".
    assert block["plan_status"] == "executed"
    # V1.6 §6 + Phase A item 2: executed runs are never a rest-day
    # violation (a day with a planned workout is not a rest day).
    assert block["violated_rest_day"] is False

    assert block["planned"] == {"type": "easy", "miles": 5.0}

    # V1.6 §6 Phase A item 3: ``deviation_direction`` lives inside
    # ``actual`` (namespace-isolation rule). Default fake activity
    # is 100% in Easy's target band → ``on_target``.
    assert block["actual"] == {
        "type": "easy",
        "miles": 5.1,
        "completion_pct": 1.02,
        "run_score": "green",
        "zone_compliance_pct": 82.5,
        "pct_above_zone": 7.0,
        "pct_below_zone": 10.5,
        "scoring_detail": None,
        "average_heartrate": 138.4,
        "deviation_direction": "on_target",
    }


def test_build_run_execution_block_deviation_direction_too_hard():
    """Easy plan, ≥15% time above target → actual.deviation_direction
    = ``too_hard``. V1.6 §5 Phase A item 3."""
    act = _FakeActivity(
        hr_zone_1=0, hr_zone_2=500, hr_zone_3=0, hr_zone_4=500, hr_zone_5=0
    )
    block = build_run_execution_block(act)
    assert block["actual"]["deviation_direction"] == "too_hard"


def test_build_run_execution_block_deviation_direction_omitted_for_steady():
    """Spec §5 Steady TODO: deviation_direction must be ``None`` for
    Steady (deferred to V1.7 — approximation forbidden)."""
    act = _FakeActivity(planned_type="steady")
    block = build_run_execution_block(act)
    assert block["actual"]["deviation_direction"] is None


def test_build_run_execution_block_deviation_direction_omitted_for_tempo_v1_6():
    """V1.6 tempo gap: no main-block-scoped metrics yet →
    ``deviation_direction`` = ``None`` for tempo. Documented in
    ``deviation.py`` module docstring."""
    act = _FakeActivity(planned_type="tempo", hr_zone_3=500, hr_zone_4=1000)
    block = build_run_execution_block(act)
    assert block["actual"]["deviation_direction"] is None


def test_build_run_execution_block_deviation_direction_omitted_short_run():
    """Spec §5 rule 2: duration < 600s → deviation_direction None."""
    act = _FakeActivity(moving_time=599)
    block = build_run_execution_block(act)
    assert block["actual"]["deviation_direction"] is None


def test_build_run_execution_block_deviation_direction_omitted_no_hr():
    """Spec §5 rule 2: HR missing (all zones zero) → None."""
    act = _FakeActivity(hr_zone_1=0, hr_zone_2=0, hr_zone_3=0, hr_zone_4=0, hr_zone_5=0)
    block = build_run_execution_block(act)
    assert block["actual"]["deviation_direction"] is None


def test_build_run_execution_block_handles_unplanned_activity():
    """
    Unplanned activity: ``matched_plan_workout_id`` and planned.* are
    ``None`` (checked, no value) per V1.6 §4 null-vs-absent convention.
    ``plan_status`` deterministically flips to ``"unplanned"``.
    """
    act = _FakeActivity(
        matched_plan_workout_id=None,
        planned_type=None,
        planned_miles=None,
    )
    block = build_run_execution_block(act)
    assert block["matched_plan_workout_id"] is None
    assert block["plan_status"] == "unplanned"
    # No plan_training_days passed → safe default False
    # (spec "false otherwise"; prevents coach escalation on
    # ambiguous plan metadata).
    assert block["violated_rest_day"] is False
    assert block["planned"] == {"type": None, "miles": None}
    assert block["actual"]["type"] == "easy"
    # V1.6 Phase A item 3: no planned_type → deviation_direction
    # omitted (None). Consistent with "the LLM must not derive
    # deviation from actual alone" (§5 + §19).
    assert block["actual"]["deviation_direction"] is None


def test_build_run_execution_block_violated_rest_day_true_on_rest_day():
    """
    V1.6 §6 Phase A item 2: unplanned activity on a planned rest day
    (weekday not in plan_training_days) → violated_rest_day=True.
    Fake activity is on 2026-04-21 (a Tuesday); training days
    exclude Tuesday → violation.
    """
    act = _FakeActivity(
        matched_plan_workout_id=None,
        planned_type=None,
        planned_miles=None,
    )
    block = build_run_execution_block(
        act, plan_training_days=["Mon", "Wed", "Thu", "Sat"]
    )
    assert block["plan_status"] == "unplanned"
    assert block["violated_rest_day"] is True


def test_build_run_execution_block_violated_rest_day_false_on_training_day():
    """Unplanned run on a day that WAS a training day → not a rest-day
    violation (it's a missed-workout + extra run scenario)."""
    act = _FakeActivity(
        matched_plan_workout_id=None,
        planned_type=None,
        planned_miles=None,
    )
    # 2026-04-21 is a Tuesday; include Tuesday in training days.
    block = build_run_execution_block(
        act, plan_training_days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    )
    assert block["plan_status"] == "unplanned"
    assert block["violated_rest_day"] is False


def test_build_run_execution_block_violated_rest_day_false_when_training_days_missing():
    """No plan_training_days → safe default False per spec 'false
    otherwise' — coach §19 must not escalate on ambiguous metadata."""
    act = _FakeActivity(
        matched_plan_workout_id=None,
        planned_type=None,
        planned_miles=None,
    )
    # Explicitly None.
    block = build_run_execution_block(act, plan_training_days=None)
    assert block["violated_rest_day"] is False
    # Also for empty list (pathological plan row).
    block = build_run_execution_block(act, plan_training_days=[])
    assert block["violated_rest_day"] is False


def test_weekly_plan_shape_dual_emit_legacy_parity_and_namespaced():
    """
    V1.6 0.E dual-emit contract: ``execution_block_to_weekly_plan_shape``
    must emit BOTH (a) the legacy flat fields in byte-exact parity with
    the pre-0.A ``plan_routes._execution_payload`` shape (backward compat
    for any non-0.E consumer) AND (b) the canonical V1.6 §6 namespaced
    ``planned`` / ``actual`` sub-objects that 0.E mobile reads.

    Drift guard: every legacy flat field must equal its namespaced
    counterpart (single source of truth per §X.5).
    """
    act = _FakeActivity()
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)

    # Legacy flat fields — byte-exact pre-0.A shape.
    assert shape["activity_id"] == 12345
    assert shape["start_date"] == "2026-04-21T12:00:00+00:00"
    assert shape["planned_type"] == "easy"
    assert shape["executed_type"] == "easy"
    assert shape["run_score"] == "green"
    assert shape["zone_compliance_pct"] == 82.5
    assert shape["planned_miles"] == 5.0
    assert shape["actual_miles"] == 5.1
    assert shape["completion_pct"] == 1.02
    assert shape["scoring_detail"] is None
    assert shape["average_heartrate"] == 138  # rounded to int for UI
    assert shape["avg_pace_per_mile"] == "9:00/mi"  # 2754 / 5.1 ≈ 540 s/mi

    # V1.6 §6 canonical namespaced shape — 0.E mobile reads these.
    assert shape["matched_plan_workout_id"] == 777
    assert shape["planned"] == {"type": "easy", "miles": 5.0}
    assert shape["actual"] == {
        "type": "easy",
        "miles": 5.1,
        "completion_pct": 1.02,
        "run_score": "green",
        "zone_compliance_pct": 82.5,
        "pct_above_zone": 7.0,
        "pct_below_zone": 10.5,
        "scoring_detail": None,
        "average_heartrate": 138,  # display-augmented: rounded int
        "avg_pace_per_mile": "9:00/mi",  # display-augmented: formatted
        # V1.6 Phase A item 3: surfaced in the namespaced actual.
        # Default Easy+in-target distribution → "on_target".
        "deviation_direction": "on_target",
    }

    # Drift guard: legacy flat fields === namespaced counterparts.
    assert shape["planned_type"] == shape["planned"]["type"]
    assert shape["planned_miles"] == shape["planned"]["miles"]
    assert shape["executed_type"] == shape["actual"]["type"]
    assert shape["actual_miles"] == shape["actual"]["miles"]
    assert shape["completion_pct"] == shape["actual"]["completion_pct"]
    assert shape["run_score"] == shape["actual"]["run_score"]
    assert shape["zone_compliance_pct"] == shape["actual"]["zone_compliance_pct"]
    assert shape["scoring_detail"] == shape["actual"]["scoring_detail"]
    assert shape["average_heartrate"] == shape["actual"]["average_heartrate"]
    assert shape["avg_pace_per_mile"] == shape["actual"]["avg_pace_per_mile"]

    # V1.6 Phase A item 1: plan_status is deliberately NOT surfaced in
    # the weekly-plan execution adapter — the ``/api/plan/current-week``
    # route carries it at the day level (see test_current_week_...).
    # This prevents day-vs-execution duplication and keeps the day as
    # the authoritative plan-status source for the primary route.
    assert "plan_status" not in shape
    # Same non-duplication rule for V1.6 Phase A item 2: the day-level
    # entry carries violated_rest_day; the execution adapter must not
    # mirror it.
    assert "violated_rest_day" not in shape


def test_weekly_plan_shape_avg_hr_none_when_missing():
    """Rounded-int HR passes through None safely."""
    act = _FakeActivity(average_heartrate=None)
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)
    assert shape["average_heartrate"] is None


def test_weekly_plan_shape_avg_pace_none_when_distance_or_time_missing():
    """Pace display falls back to None when inputs are missing/zero."""
    for kwargs in (
        {"conv_distance": None},
        {"conv_distance": 0},
        {"moving_time": None},
        {"moving_time": 0},
    ):
        act = _FakeActivity(**kwargs)
        shape = execution_block_to_weekly_plan_shape(
            build_run_execution_block(act), act
        )
        assert (
            shape["avg_pace_per_mile"] is None
        ), f"pace must be None when {kwargs} produces undefined rate"


def test_weekly_plan_shape_start_date_none_when_missing():
    """No start_date → None (not a crash)."""
    act = _FakeActivity(start_date=None)
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)
    assert shape["start_date"] is None


def test_insight_summary_shape_parity_with_pre_0a_dict_literal():
    """
    Shape contract for ``execution_block_to_insight_summary_shape``.

    Pre-0.A fields are preserved byte-exact. V1.6 Phase A additions
    (``plan_status`` — Phase A item 1) are surfaced so the LLM
    ``get_run_summary`` tool has all deterministic fields available.
    Further Phase A fields will be added here in subsequent items.
    """
    block = build_run_execution_block(_FakeActivity())
    summary = execution_block_to_insight_summary_shape(block)

    # V1.6 Phase B 3B.1 dual-emit shape: top-level pairing controllers
    # + canonical §6 ``planned`` / ``actual`` namespaced blocks +
    # legacy flat scalars. Every value is sourced from the same
    # canonical ``block`` (no recompute) — this assertion is the
    # single-source-of-truth contract lock.
    assert summary == {
        "matched_plan_workout_id": 777,
        "plan_status": "executed",
        "violated_rest_day": False,
        # V1.6 §6 canonical namespaced blocks — Phase B 3B.1.
        "planned": {"type": "easy", "miles": 5.0},
        "actual": {
            "type": "easy",
            "miles": 5.1,
            "completion_pct": 1.02,
            "run_score": "green",
            "zone_compliance_pct": 82.5,
            "pct_above_zone": 7.0,
            "pct_below_zone": 10.5,
            "scoring_detail": None,
            "average_heartrate": 138.4,
            "deviation_direction": "on_target",
        },
        # Top-level convenience copy of ``actual.deviation_direction``.
        "deviation_direction": "on_target",
        # Legacy flat scalars — DEPRECATED V1.7.
        "planned_type": "easy",
        "executed_type": "easy",
        "zone_compliance_pct": 82.5,
        "pct_above_zone": 7.0,
        "pct_below_zone": 10.5,
        "run_score": "green",
        "planned_miles": 5.0,
        "actual_miles": 5.1,
        "completion_pct": 1.02,
    }


def test_insight_summary_shape_namespaced_blocks_match_source_block():
    """
    V1.6 Phase B 3B.1 single-source-of-truth contract: the
    ``planned`` and ``actual`` sub-dicts in the insight-summary
    shape must be byte-exact copies of the corresponding blocks
    on the canonical source. Any adapter-level massaging would
    drift the LLM view from the mobile view and break the "one
    source" guarantee in PHASE_3_IMPLEMENTATION_CHECKLIST §X.5.
    """
    block = build_run_execution_block(_FakeActivity())
    summary = execution_block_to_insight_summary_shape(block)

    assert summary["planned"] == block["planned"]
    assert summary["actual"] == block["actual"]
    # Identity must not be shared (adapter returns a copy so a
    # downstream cache mutation on either side stays local).
    assert summary["planned"] is not block["planned"]
    assert summary["actual"] is not block["actual"]


def test_insight_summary_shape_top_level_controllers_match_source_block():
    """
    V1.6 §6 + Phase B 3B.1: ``plan_status``, ``violated_rest_day``,
    ``matched_plan_workout_id`` live at the top level of the insight
    summary because they describe the pairing between plan and
    actual (§19 non-overrideable deterministic fields — the coach
    validator in Phase C keys on these exact top-level names).
    """
    block = build_run_execution_block(_FakeActivity(matched_plan_workout_id=None))
    summary = execution_block_to_insight_summary_shape(block)

    assert summary["matched_plan_workout_id"] is None
    assert summary["plan_status"] == "unplanned"
    assert summary["violated_rest_day"] is False
    # Top-level deviation_direction mirrors actual.deviation_direction
    # (source of truth is actual.*; top-level is a convenience copy).
    assert summary["deviation_direction"] == summary["actual"]["deviation_direction"]


def test_insight_summary_shape_flips_plan_status_for_unplanned():
    """Activity with no matched_plan_workout_id → plan_status='unplanned'."""
    act = _FakeActivity(matched_plan_workout_id=None)
    summary = execution_block_to_insight_summary_shape(build_run_execution_block(act))
    assert summary["matched_plan_workout_id"] is None
    assert summary["plan_status"] == "unplanned"
    # Without training_days context, safe default.
    assert summary["violated_rest_day"] is False


def test_insight_summary_shape_carries_deviation_direction_too_hard():
    """V1.6 §5 Phase A item 3: a too-hard Easy run must reach the
    LLM via ``summary.deviation_direction == 'too_hard'`` — the
    coach uses this to decide correction vs progression (§19)."""
    act = _FakeActivity(
        hr_zone_1=0, hr_zone_2=500, hr_zone_3=0, hr_zone_4=500, hr_zone_5=0
    )
    summary = execution_block_to_insight_summary_shape(build_run_execution_block(act))
    assert summary["deviation_direction"] == "too_hard"


def test_insight_summary_shape_carries_violated_rest_day_true():
    """LLM tool must see violated_rest_day=True when it applies (§19.7
    stronger-tone requirement depends on this flag)."""
    act = _FakeActivity(matched_plan_workout_id=None)  # Tue 2026-04-21
    summary = execution_block_to_insight_summary_shape(
        build_run_execution_block(act, plan_training_days=["Mon", "Wed", "Thu", "Sat"])
    )
    assert summary["plan_status"] == "unplanned"
    assert summary["violated_rest_day"] is True


def test_both_adapters_share_the_same_source_block():
    """
    Single-source-of-truth rule (PHASE_3_IMPLEMENTATION_CHECKLIST §X.5):
    both adapters read the same extracted values from the canonical
    block, so any field present in both shapes must carry identical
    values.
    """
    act = _FakeActivity()
    block = build_run_execution_block(act)
    weekly = execution_block_to_weekly_plan_shape(block, act)
    summary = execution_block_to_insight_summary_shape(block)

    for key in (
        "planned_type",
        "executed_type",
        "run_score",
        "zone_compliance_pct",
        "planned_miles",
        "actual_miles",
        "completion_pct",
    ):
        assert weekly[key] == summary[key], (
            f"drift between weekly-plan adapter and insight-summary adapter "
            f"on '{key}': {weekly[key]!r} vs {summary[key]!r}"
        )


def test_build_run_execution_block_accepts_duck_typed_input():
    """
    ``build_run_execution_block`` uses ``getattr(act, ..., None)`` — any
    duck-typed object with the canonical attributes should work. This
    locks in the Protocol-like contract so tests and future refactors
    don't need to instantiate full SQLAlchemy ``Activity`` rows.
    """
    duck = SimpleNamespace(
        matched_plan_workout_id=1,
        planned_type="long",
        planned_miles=12.0,
        executed_type="long",
        actual_miles=12.1,
        completion_pct=1.008,
        run_score="green",
        zone_compliance_pct=78.0,
        pct_above_zone=5.0,
        pct_below_zone=17.0,
        scoring_detail={"band": "green"},
        average_heartrate=145.2,
    )
    block = build_run_execution_block(duck)
    assert block["planned"]["type"] == "long"
    assert block["actual"]["scoring_detail"] == {"band": "green"}
