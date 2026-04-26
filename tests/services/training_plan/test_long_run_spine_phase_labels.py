"""Regression tests for Base / Build / Specific / Taper spine labeling."""

from __future__ import annotations

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    SPECIFIC_LR_THRESHOLD_RATIO,
    assign_training_intent_phases,
    generate_long_run_spine,
)


def test_assign_training_intent_phases_specific_threshold_and_peak_flag():
    weeks = [
        {"week_number": 1, "long_run_miles": 10.0, "phase": ""},
        {"week_number": 2, "long_run_miles": 12.0, "phase": ""},
        {"week_number": 3, "long_run_miles": 18.0, "phase": ""},  # >= 0.9 * 19
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


def test_specific_threshold_constant():
    assert 0.85 < SPECIFIC_LR_THRESHOLD_RATIO < 0.95
