"""Regression tests for Base / Build / Specific / Taper spine labeling."""

from __future__ import annotations

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    SPECIFIC_LR_MILES_BELOW_PEAK,
    SPECIFIC_PLATEAU_MAX_DELTA_MI,
    SPECIFIC_PLATEAU_MAX_MILES_BELOW_PEAK,
    assign_training_intent_phases,
    generate_long_run_spine,
)


def test_assign_training_intent_phases_near_peak_floor_and_peak_flag():
    weeks = [
        {"week_number": 1, "long_run_miles": 10.0, "phase": ""},
        {"week_number": 2, "long_run_miles": 12.0, "phase": ""},
        {"week_number": 3, "long_run_miles": 18.0, "phase": ""},  # >= 19 - 2
        {"week_number": 4, "long_run_miles": 19.0, "phase": ""},
        {"week_number": 5, "long_run_miles": 17.0, "phase": ""},
        {"week_number": 6, "long_run_miles": 12.0, "phase": ""},
    ]
    assign_training_intent_phases(weeks, taper_weeks=2)
    assert [w["phase"] for w in weeks] == [
        "Base",
        "Build",
        "Specific",
        "Specific",
        "Taper",
        "Taper",
    ]
    assert sum(1 for w in weeks if w.get("is_peak_week")) == 1
    assert weeks[3]["is_peak_week"] is True  # first week at global max LR (19.0)


def test_assign_training_intent_phases_plateau_requires_two_consecutive_weeks():
    """Two consecutive weeks: both LR >= peak-3, |Δ| <= 1 → Specific from first of pair."""
    weeks = [
        {"week_number": 1, "long_run_miles": 15.0, "phase": ""},
        {"week_number": 2, "long_run_miles": 16.0, "phase": ""},
        {"week_number": 3, "long_run_miles": 16.5, "phase": ""},
        {"week_number": 4, "long_run_miles": 19.0, "phase": ""},
        {"week_number": 5, "long_run_miles": 12.0, "phase": ""},
    ]
    assign_training_intent_phases(weeks, taper_weeks=1)
    assert [w["phase"] for w in weeks] == [
        "Base",
        "Specific",
        "Specific",
        "Specific",
        "Taper",
    ]
    assert weeks[3]["is_peak_week"] is True


def test_assign_training_intent_phases_single_week_near_peak_no_plateau_pair_stays_build():
    """One week at 16.5 after 14 does not satisfy two-week plateau; near-peak starts at 17+."""
    weeks = [
        {"week_number": 1, "long_run_miles": 14.0, "phase": ""},
        {"week_number": 2, "long_run_miles": 16.5, "phase": ""},
        {"week_number": 3, "long_run_miles": 19.0, "phase": ""},
        {"week_number": 4, "long_run_miles": 12.0, "phase": ""},
    ]
    assign_training_intent_phases(weeks, taper_weeks=1)
    # peak 19: near-peak floor 17; week2 16.5 < 17; plateau pair (14,16.5) fails both >= 16
    assert [w["phase"] for w in weeks] == ["Base", "Build", "Specific", "Taper"]


def test_generate_long_run_spine_no_peak_phase_label_25_weeks():
    config = MarathonConfig()
    weeks = generate_long_run_spine(
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
    assert "Peak" not in phases
    assert "Specific" in phases
    assert phases[-config.taper_weeks :] == ["Taper"] * config.taper_weeks
    assert sum(1 for w in weeks if w.get("is_peak_week")) == 1

    first_spec = next(i for i, p in enumerate(phases) if p == "Specific")
    assert "Build" not in phases[first_spec : -config.taper_weeks]


def test_generate_long_run_spine_dynamic_mode_labels():
    config = MarathonConfig()
    weeks = generate_long_run_spine(
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
    assert "Peak" not in phases
    assert "Specific" in phases or "Taper" in phases
    assert all("is_peak_week" in w for w in weeks)


def test_specific_constants_are_absolute_miles():
    assert SPECIFIC_LR_MILES_BELOW_PEAK == 2.0
    assert SPECIFIC_PLATEAU_MAX_DELTA_MI == 1.0
    assert SPECIFIC_PLATEAU_MAX_MILES_BELOW_PEAK == 3.0
