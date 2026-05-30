"""Unit tests for :mod:`src.services.plan.planned_workout_weekly_wire`."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.plan.planned_workout_weekly_wire import (
    build_planned_weekly_wire,
    merge_planned_wire_into_execution_shape,
    planned_pace_display_string,
)


def test_planned_pace_display_string_band_from_pace_ranges():
    w = SimpleNamespace(
        miles=5.0,
        intensity="z2",
        run_type_key="easy",
        pace_ranges={"z2": [480, 510]},
    )
    s = planned_pace_display_string(w)
    assert s == "8:00-8:30/mi"


def test_build_planned_weekly_wire_includes_target_pace_display_when_ranges():
    w = SimpleNamespace(
        miles=5.0,
        intensity="z2",
        run_type_key="easy",
        pace_ranges={"z2": [480, 480]},
    )
    wire = build_planned_weekly_wire(
        w, canonical_run_type_key="easy", target_hr="Z2 (120-150 bpm)"
    )
    assert wire["display_planned"]["miles"] == "5.00 mi"
    assert wire["display_planned"]["target_hr"] == "Z2 (120-150 bpm)"
    assert "pace" in wire["display_planned"]
    assert (
        wire["execution_planned"]["target_pace_display"]
        == wire["display_planned"]["pace"]
    )


def test_merge_planned_wire_overwrites_execution_planned_and_display():
    wire = build_planned_weekly_wire(
        SimpleNamespace(
            miles=6.0,
            intensity="z3",
            run_type_key="easy",
            pace_ranges={"z3": [420, 450]},
        ),
        canonical_run_type_key="easy",
        target_hr=None,
    )
    shape: dict = {
        "planned": {"type": "easy", "miles": 99.0},
        "planned_type": "easy",
        "planned_miles": 99.0,
        "display": {"planned": {"miles": "wrong", "target_hr": "x"}, "actual": {}},
    }
    merge_planned_wire_into_execution_shape(shape, wire)
    assert shape["planned"]["type"] == "steady"
    assert shape["planned"]["miles"] == 6.0
    assert shape["planned_miles"] == 6.0
    assert shape["display"]["planned"]["miles"] == "6.00 mi"
    assert shape["display"]["planned"]["pace"] == "7:00-7:30/mi"
