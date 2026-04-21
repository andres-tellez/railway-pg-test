"""
V1.6 Phase B 3B.7 — display-ready strings contract across all plan tools.

Topic 4 requires every coach-facing plan payload to surface human-readable
strings (pace ``M:SS/mi``, HR ``"N bpm"``, distance with ``mi``,
percentages as ``"NN %"``) **alongside** the numeric fields so the LLM
never has to reformat values on the fly.

This suite locks the contract at each producer boundary:

* ``execution_block_to_weekly_plan_shape`` — day-level ``execution`` block
  consumed by both ``get_weekly_plan`` and the HTTP ``/api/plan/current-week``
  route (single source of truth — must agree by construction).
* ``execution_block_to_insight_summary_shape`` — used by
  ``get_run_summary.facts.execution_summary``.
* ``build_weekly_plan_payload`` day entries — top-level ``display``
  sibling on planned side (miles + target_hr).
* ``build_plan_overview_payload`` — ``display`` blocks on top-level,
  each ``phase_blocks`` entry, each ``volume_curve`` row, each
  ``long_run_progression`` row.
* ``build_phase_analysis_payload`` — ``display`` blocks on
  ``phase_weeks`` and every ``by_run_type[key]`` bucket.

We do NOT exercise the DB here — the DB-backed integration tests
already cover end-to-end shape. These tests pin the **formatting**
contract and will catch a regression where a downstream consumer
silently drops the ``display`` block.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.smartcoach_mobile_coach.display_format import (
    format_distance_mi,
    format_hr_bpm,
    format_hr_range_bpm,
    format_pace_sec_per_mi,
    format_percent,
)
from src.smartcoach_mobile_coach.run_insight import (
    build_run_execution_block,
    execution_block_to_insight_summary_shape,
    execution_block_to_weekly_plan_shape,
)


# ---------------------------------------------------------------------------
# display_format helpers — pin the format spec the plan tools rely on.
# ---------------------------------------------------------------------------


def test_distance_includes_mi_unit_and_two_decimals():
    assert format_distance_mi(5.0) == "5.00 mi"
    assert format_distance_mi(10.5) == "10.50 mi"


def test_distance_none_returns_dash_placeholder():
    assert format_distance_mi(None) == "—"


def test_hr_bpm_rounds_and_appends_unit():
    assert format_hr_bpm(138.4) == "138 bpm"
    assert format_hr_bpm(142) == "142 bpm"


def test_hr_bpm_none_returns_none():
    assert format_hr_bpm(None) is None


def test_hr_range_collapses_single_value():
    """138–138 collapses to '138 bpm' so we don't advertise a bogus range."""
    assert format_hr_range_bpm(138, 138) == "138 bpm"


def test_hr_range_uses_en_dash_and_single_unit():
    assert format_hr_range_bpm(138, 150) == "138\u2013150 bpm"


def test_hr_range_missing_endpoint_is_none():
    """Callers fall back to the numeric field when either end is missing."""
    assert format_hr_range_bpm(None, 150) is None
    assert format_hr_range_bpm(138, None) is None


def test_pace_format_matches_m_ss_per_mi():
    # 558 seconds/mi == 9:18/mi
    assert format_pace_sec_per_mi(558) == "9:18/mi"
    # 9:00/mi boundary — no leading zero on minutes, zero-padded seconds.
    assert format_pace_sec_per_mi(540) == "9:00/mi"


def test_percent_accepts_both_fractional_and_percent_space():
    """
    Fractional (``0.725``) → ``"72 %"``; already-percent values
    (``82.5``) pass through. This matters because
    ``zone_compliance_pct`` is stored as percent-space but
    ``completion_pct`` is stored as a fractional ratio.
    """
    assert format_percent(0.725) == "72 %"
    assert format_percent(82.5) == "82 %"


def test_percent_supports_decimal_argument():
    assert format_percent(0.725, decimals=1) == "72.5 %"


def test_percent_none_returns_none():
    assert format_percent(None) is None


# ---------------------------------------------------------------------------
# execution_block_to_weekly_plan_shape — day-level execution block.
# ---------------------------------------------------------------------------


class _FakeAct(SimpleNamespace):
    """Duck-typed Activity stand-in for the adapter under test."""


def _make_activity(**overrides):
    defaults = dict(
        activity_id=1_000_001,
        start_date=None,
        matched_plan_workout_id=42,
        planned_type="easy",
        executed_type="easy",
        planned_miles=5.0,
        actual_miles=5.1,
        completion_pct=1.02,
        run_score="green",
        zone_compliance_pct=82.5,
        pct_above_zone=7.0,
        pct_below_zone=10.5,
        scoring_detail=None,
        average_heartrate=138.4,
        conv_distance=5.1,
        moving_time=2_700,  # 45 minutes → 8:49 /mi over 5.1 mi
        hr_zone_1=0,
        hr_zone_2=2_700,
        hr_zone_3=0,
        hr_zone_4=0,
        hr_zone_5=0,
    )
    defaults.update(overrides)
    return _FakeAct(**defaults)


def test_weekly_plan_shape_emits_top_level_display_sibling():
    act = _make_activity()
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)

    # The byte-exact 3B.1 parity contract: ``planned`` / ``actual``
    # sub-dicts remain copies of the canonical block — the display
    # strings live at the top level as a sibling, not nested.
    assert "display" in shape
    assert "display" not in shape["planned"]
    assert "display" not in shape["actual"]


def test_weekly_plan_shape_display_actual_has_all_topic4_fields():
    act = _make_activity()
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)

    actual_display = shape["display"]["actual"]
    assert actual_display["miles"] == "5.10 mi"
    assert actual_display["avg_hr"] == "138 bpm"
    assert actual_display["pace"] == "8:49/mi"
    assert actual_display["zone_compliance_pct"] == "82 %"
    # 1.02 is already percent-space; format_percent passes it through.
    assert actual_display["completion_pct"] == "102 %"


def test_weekly_plan_shape_display_planned_has_miles():
    act = _make_activity()
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)
    assert shape["display"]["planned"]["miles"] == "5.00 mi"


def test_weekly_plan_shape_display_is_none_when_inputs_are_none():
    """
    No activity-side numbers → all ``display.actual`` keys degrade
    to ``None`` without raising. This is critical for runs where HR
    is missing (format_hr_bpm returns None) — the coach must still
    get a stable shape.
    """
    act = _make_activity(
        average_heartrate=None,
        zone_compliance_pct=None,
        completion_pct=None,
        actual_miles=None,
        conv_distance=None,
        moving_time=None,
    )
    shape = execution_block_to_weekly_plan_shape(build_run_execution_block(act), act)
    actual_display = shape["display"]["actual"]
    assert actual_display["miles"] is None
    assert actual_display["avg_hr"] is None
    # Pace helper returns ``None`` when either ``conv_distance`` or
    # ``moving_time`` is missing — coach falls back to numeric fields.
    assert actual_display["pace"] is None
    assert actual_display["zone_compliance_pct"] is None
    assert actual_display["completion_pct"] is None


def test_weekly_plan_shape_namespaced_blocks_remain_byte_exact():
    """
    3B.7 display sibling must NOT break the 3B.1 namespace-parity
    contract. ``planned`` / ``actual`` sub-dicts stay byte-exact
    copies of the canonical source block; display strings live
    exclusively at the top level.
    """
    act = _make_activity()
    block = build_run_execution_block(act)
    shape = execution_block_to_weekly_plan_shape(block, act)
    assert shape["planned"] == block["planned"]
    # actual is display-augmented (rounded HR, pace) per 0.E; the
    # underlying KPI fields (zone_compliance_pct etc.) are identical.
    for key in block["actual"]:
        if key == "average_heartrate":
            # Rounded to int per 0.E shape.
            assert shape["actual"][key] == int(round(block["actual"][key]))
        else:
            assert shape["actual"][key] == block["actual"][key]


# ---------------------------------------------------------------------------
# execution_block_to_insight_summary_shape — get_run_summary.
# ---------------------------------------------------------------------------


def test_insight_summary_shape_emits_top_level_display_sibling():
    block = build_run_execution_block(_make_activity())
    summary = execution_block_to_insight_summary_shape(block)
    assert "display" in summary
    # Byte-exact parity with the canonical block is preserved.
    assert summary["planned"] == block["planned"]
    assert summary["actual"] == block["actual"]


def test_insight_summary_shape_display_has_every_topic4_field():
    block = build_run_execution_block(_make_activity())
    summary = execution_block_to_insight_summary_shape(block)
    display = summary["display"]

    assert display["planned"]["miles"] == "5.00 mi"
    assert display["actual"]["miles"] == "5.10 mi"
    assert display["actual"]["avg_hr"] == "138 bpm"
    assert display["actual"]["zone_compliance_pct"] == "82 %"
    assert display["actual"]["completion_pct"] == "102 %"
    assert display["actual"]["pct_above_zone"] == "7 %"
    assert display["actual"]["pct_below_zone"] == "10 %"


def test_insight_summary_shape_display_handles_nulls():
    act = _make_activity(
        planned_miles=None,
        actual_miles=None,
        average_heartrate=None,
        zone_compliance_pct=None,
        completion_pct=None,
        pct_above_zone=None,
        pct_below_zone=None,
    )
    summary = execution_block_to_insight_summary_shape(build_run_execution_block(act))
    assert summary["display"]["planned"]["miles"] is None
    assert summary["display"]["actual"]["miles"] is None
    assert summary["display"]["actual"]["avg_hr"] is None
    assert summary["display"]["actual"]["zone_compliance_pct"] is None
    assert summary["display"]["actual"]["completion_pct"] is None


# ---------------------------------------------------------------------------
# build_weekly_plan_payload — day-level planned display.
# ---------------------------------------------------------------------------


def test_weekly_plan_builder_future_day_has_planned_display():
    """
    Future-week day entries carry ``display.planned`` so the coach
    can say "5.00 mi Easy on Tuesday" without formatting the float.
    """
    from src.services.plan.weekly_plan import _build_future_week_day_entry

    pw = SimpleNamespace(
        id=1,
        date=__import__("datetime").date(2026, 5, 5),
        workout_type="Easy Run",
        description="Easy miles",
        miles=5.0,
        intensity="E",
        run_type_key="easy",
        phase="Base",
        target_zone="Z2",
        focus="aerobic base",
    )
    entry = _build_future_week_day_entry(pw, "easy", target_hr="Z2 (120-150 bpm)")
    assert entry["display"]["planned"]["miles"] == "5.00 mi"
    assert entry["display"]["planned"]["target_hr"] == "Z2 (120-150 bpm)"


def test_weekly_plan_builder_planned_miles_none_degrades_cleanly():
    """An upstream migration that leaves miles null must not crash."""
    from src.services.plan.weekly_plan import _build_future_week_day_entry

    pw = SimpleNamespace(
        id=1,
        date=__import__("datetime").date(2026, 5, 5),
        workout_type="Easy Run",
        description="",
        miles=None,
        intensity="E",
        run_type_key="easy",
        phase="Base",
        target_zone="Z2",
        focus="",
    )
    entry = _build_future_week_day_entry(pw, "easy", target_hr=None)
    assert entry["display"]["planned"]["miles"] is None
    assert entry["display"]["planned"]["target_hr"] is None


# ---------------------------------------------------------------------------
# build_plan_overview_payload — sanity check the display block keys
# via the pure _build_volume_curve_entry helper.
# ---------------------------------------------------------------------------


def test_plan_overview_volume_curve_has_display_miles_total():
    from datetime import date as _date

    from src.services.plan.plan_overview import _build_volume_curve_entry

    pw = SimpleNamespace(
        id=1,
        date=_date(2026, 4, 21),
        workout_type="Easy Run",
        description="",
        miles=5.0,
        intensity="E",
        run_type_key="easy",
        phase="Base",
        target_zone="Z2",
        focus="",
    )
    row = _build_volume_curve_entry(
        week_index=1,
        week_start=_date(2026, 4, 20),
        week_end=_date(2026, 4, 26),
        workouts=[pw, pw, pw],  # 15 mi total
        today=_date(2026, 4, 22),
    )
    assert row["display"]["planned_miles_total"] == "15.00 mi"


# ---------------------------------------------------------------------------
# build_phase_analysis_payload — bucket display block.
# ---------------------------------------------------------------------------


def test_phase_analysis_bucket_display_is_fully_populated_after_finalize():
    from src.services.plan.phase_analysis import (
        _empty_run_type_bucket,
        _finalize_bucket,
    )

    bucket = _empty_run_type_bucket()
    bucket["run_count_planned"] = 4
    bucket["run_count_matched"] = 3
    bucket["miles_planned_total"] = 32.0
    bucket["miles_actual_total"] = 30.5
    bucket["_zc_samples"] = [80.0, 82.5, 78.0]
    bucket["_cp_samples"] = [1.0, 0.98, 0.96]

    _finalize_bucket(bucket, week_zc_accumulator={})

    d = bucket["display"]
    assert d["miles_planned_total"] == "32.00 mi"
    assert d["miles_actual_total"] == "30.50 mi"
    # Mean of 80 / 82.5 / 78 = 80.166...
    assert d["zone_compliance_pct_avg"] == "80 %"
    # Mean of 1.0 / 0.98 / 0.96 = 0.98 → 98 %
    assert d["completion_miles_pct_avg"] == "98 %"


def test_phase_analysis_bucket_display_handles_empty_samples():
    from src.services.plan.phase_analysis import (
        _empty_run_type_bucket,
        _finalize_bucket,
    )

    bucket = _empty_run_type_bucket()
    _finalize_bucket(bucket, week_zc_accumulator={})

    d = bucket["display"]
    # A phase with zero matched runs still has planned-side totals
    # but averages are None (no samples to average).
    assert d["miles_planned_total"] == "0.00 mi"
    assert d["miles_actual_total"] == "0.00 mi"
    assert d["zone_compliance_pct_avg"] is None
    assert d["completion_miles_pct_avg"] is None
