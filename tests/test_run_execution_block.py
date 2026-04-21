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


def test_build_run_execution_block_namespaced_shape():
    """
    V1.6 §6 contract: planned.* and actual.* are strictly separated.
    ``matched_plan_workout_id`` is metadata and lives outside the
    namespaces.
    """
    block = build_run_execution_block(_FakeActivity())
    assert set(block.keys()) == {"matched_plan_workout_id", "planned", "actual"}
    assert block["matched_plan_workout_id"] == 777

    assert block["planned"] == {"type": "easy", "miles": 5.0}

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
    }


def test_build_run_execution_block_handles_unplanned_activity():
    """
    Unplanned activity: ``matched_plan_workout_id`` and planned.* are
    ``None`` (checked, no value) per V1.6 §4 null-vs-absent convention.
    """
    act = _FakeActivity(
        matched_plan_workout_id=None,
        planned_type=None,
        planned_miles=None,
    )
    block = build_run_execution_block(act)
    assert block["matched_plan_workout_id"] is None
    assert block["planned"] == {"type": None, "miles": None}
    assert block["actual"]["type"] == "easy"


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
    Byte-exact parity: ``execution_block_to_insight_summary_shape`` must
    produce the exact dict the pre-0.A ``facts.execution_summary`` dict
    literal produced. If any field drifts, the LLM ``get_run_summary``
    contract changes silently.
    """
    block = build_run_execution_block(_FakeActivity())
    summary = execution_block_to_insight_summary_shape(block)

    assert summary == {
        "matched_plan_workout_id": 777,
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
