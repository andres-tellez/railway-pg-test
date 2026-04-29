"""Regression tests for Base / Build / Peak / Taper spine labeling (fixed Peak window)."""

from __future__ import annotations

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    _bump_adjacent_duplicate_peak_long_runs_revisit,
    _coached_peak_long_run_miles,
    assign_training_intent_phases,
    build_long_run_spine_weeks,
    capped_peak_training_weeks,
    compute_cutback_long_run_miles,
)


def test_compute_cutback_caps_large_regressions():
    # Harsh factor would yield 10.5 from 14; floors keep deload to a 2 mi / 20% band.
    assert compute_cutback_long_run_miles(14.0, 0.75, 5.0) == 12.0
    assert compute_cutback_long_run_miles(16.0, 0.75, 5.0) == 14.0


def test_capped_peak_training_weeks_table():
    assert capped_peak_training_weeks(10) == 3
    assert capped_peak_training_weeks(16) == 3
    assert capped_peak_training_weeks(17) == 3
    assert capped_peak_training_weeks(21) == 3
    assert capped_peak_training_weeks(22) == 4
    assert capped_peak_training_weeks(24) == 4
    assert capped_peak_training_weeks(25) == 4
    assert capped_peak_training_weeks(40) == 4


def test_bump_adjacent_duplicate_peak_long_runs_revisit_breaks_plateau() -> None:
    """Guardrail: equal adjacent Peak LRs get a small step when below ``hi``."""
    peak = [18.0, 18.0, 20.0, 19.0]
    _bump_adjacent_duplicate_peak_long_runs_revisit(
        peak, 17.0, 20.0, round_to_half=True, unit_system="imperial"
    )
    assert peak == [18.0, 18.5, 20.0, 19.0]


def test_bump_adjacent_duplicate_peak_long_runs_revisit_whole_mile_step() -> None:
    peak = [18.0, 18.0]
    _bump_adjacent_duplicate_peak_long_runs_revisit(
        peak, 17.0, 20.0, round_to_half=False, unit_system="imperial"
    )
    assert peak == [18.0, 19.0]


def test_bump_adjacent_duplicate_peak_long_runs_revisit_no_room_at_ceiling() -> None:
    peak = [20.0, 20.0]
    _bump_adjacent_duplicate_peak_long_runs_revisit(
        peak, 18.0, 20.0, round_to_half=True, unit_system="imperial"
    )
    assert peak == [20.0, 20.0]


def test_coached_peak_four_week_ramp_no_duplicate_opening_weeks() -> None:
    """Peak block should step up by half miles (no 18, 18, 20 plateaus)."""
    out = _coached_peak_long_run_miles(
        4, 17.0, 20.0, round_to_half=True, unit_system="imperial"
    )
    assert out == [18.0, 18.5, 20.0, 19.0]
    assert out[1] > out[0]
    assert out[2] > out[1]
    assert out[3] < out[2]


def test_coached_peak_band_175_195_no_colliding_whole_mile_display() -> None:
    """17.5 vs 18.0 spine both round to 18 mi in the UI; bump week 2 to 18.5 (→19)."""
    out = _coached_peak_long_run_miles(
        4, 17.5, 19.5, round_to_half=True, unit_system="imperial"
    )
    assert out[:2] == [17.5, 18.5]
    assert out[2] == 19.5


def test_assign_training_intent_phases_trailing_peak_and_peak_flag():
    # n=6, taper 2 → pre_count=4; total_weeks 6 → K=3; Peak = last 3 weeks (indices 1,2,3)
    weeks = [
        {"week_number": 1, "long_run_miles": 10.0, "phase": ""},
        {"week_number": 2, "long_run_miles": 14.0, "phase": ""},
        {"week_number": 3, "long_run_miles": 18.0, "phase": ""},
        {"week_number": 4, "long_run_miles": 19.0, "phase": ""},
        {"week_number": 5, "long_run_miles": 12.0, "phase": ""},
        {"week_number": 6, "long_run_miles": 8.0, "phase": ""},
    ]
    assign_training_intent_phases(weeks, taper_weeks=2)
    assert [w["phase"] for w in weeks] == [
        "Base",
        "Peak",
        "Peak",
        "Peak",
        "Taper",
        "Taper",
    ]
    assert sum(1 for w in weeks if w.get("is_peak_week")) == 1
    assert weeks[3]["is_peak_week"] is True


def test_generate_long_run_spine_peak_block_length_25_weeks():
    config = MarathonConfig()
    weeks = build_long_run_spine_weeks(
        starting_long_run_miles=13.0,
        total_weeks_in_plan=25,
        peak_long_run_target=19.0,
        race_date="2026-10-11",
        taper_weeks=config.taper_weeks,
        inc_miles=config.long_run_increment,
        cutback_every=config.cutback_every,
        cutback_factor=config.cutback_factor,
        config=config,
    )
    phases = [w.get("phase") for w in weeks]
    assert "Specific" not in phases
    assert phases.count("Peak") == capped_peak_training_weeks(len(weeks))
    assert phases[-config.taper_weeks :] == ["Taper"] * config.taper_weeks
    assert sum(1 for w in weeks if w.get("is_peak_week")) == 1

    first_peak_phase = next(i for i, p in enumerate(phases) if p == "Peak")
    assert "Build" not in phases[first_peak_phase : -config.taper_weeks]


def test_generate_long_run_spine_dynamic_mode_labels():
    config = MarathonConfig()
    weeks = build_long_run_spine_weeks(
        starting_long_run_miles=8.0,
        total_weeks_in_plan=0,
        peak_long_run_target=18.0,
        taper_weeks=config.taper_weeks,
        inc_miles=config.long_run_increment,
        cutback_every=config.cutback_every,
        cutback_factor=config.cutback_factor,
        config=config,
    )
    phases = [w.get("phase") for w in weeks]
    assert "Specific" not in phases
    k = capped_peak_training_weeks(len(weeks))
    assert phases.count("Peak") == min(k, len(weeks) - config.taper_weeks)
    assert all("is_peak_week" in w for w in weeks)
