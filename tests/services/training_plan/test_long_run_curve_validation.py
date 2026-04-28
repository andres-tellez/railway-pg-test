"""Tests for centralized long-run curve validation (Stage B)."""

from __future__ import annotations

from datetime import date

import pytest

from src.services.training_plan.v2.race_configs.marathon_config import MarathonConfig
from src.services.training_plan.v2.shared_v2.long_run_curve_validation import (
    validate_long_run_curve,
)
from src.services.training_plan.v2.shared_v2.long_run_spine_v2 import (
    build_target_long_run_curve,
)


@pytest.fixture
def marathon_cfg() -> MarathonConfig:
    return MarathonConfig()


def test_validate_long_run_curve_valid_golden_marathon_curve(
    marathon_cfg: MarathonConfig,
) -> None:
    curve = build_target_long_run_curve(
        10.0,
        20,
        18.0,
        race_date=date(2026, 10, 10),
        taper_weeks=3,
        inc_miles=1.0,
        cutback_every=4,
        cutback_factor=0.85,
        peak_offset_before_taper=2,
        config=marathon_cfg,
        unit_system="imperial",
    )
    issues = validate_long_run_curve(
        curve,
        marathon_cfg,
        spine_rows=None,
        expected_start_miles=None,
        peak_target_miles=18.0,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=4,
        taper_weeks_override=int(marathon_cfg.taper_weeks),
        include_structure_checks=False,
        include_peak_max_check=True,
        include_pass1_progression=False,
        include_phase_quality=True,
    )
    assert issues == []


def test_validate_long_run_curve_bad_cutback_spacing(
    marathon_cfg: MarathonConfig,
) -> None:
    """Two cutbacks two build-weeks apart should trigger phase_cutback_spacing."""
    peak = 20.0
    curve = [
        10.0,
        11.0,
        12.0,
        10.0,
        11.0,
        10.0,
        12.0,
        13.0,
        14.0,
        15.0,
        16.0,
        17.0,
        18.0,
        19.0,
        20.0,
        15.0,
        12.0,
        8.0,
    ]
    issues = validate_long_run_curve(
        curve,
        marathon_cfg,
        spine_rows=None,
        expected_start_miles=None,
        peak_target_miles=peak,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=4,
        taper_weeks_override=3,
        include_structure_checks=False,
        include_peak_max_check=False,
        include_pass1_progression=False,
        include_phase_quality=True,
    )
    codes = [i["code"] for i in issues]
    assert "phase_cutback_spacing" in codes


def test_validate_long_run_curve_no_peak_in_build(
    marathon_cfg: MarathonConfig,
) -> None:
    """Build segment never reaches peak - 1 mi tolerance below target peak (phase check)."""
    peak = 20.0
    curve = [8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 12.0, 10.0, 8.0, 6.0]
    issues = validate_long_run_curve(
        curve,
        marathon_cfg,
        spine_rows=None,
        expected_start_miles=None,
        peak_target_miles=peak,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=int(marathon_cfg.cutback_every),
        taper_weeks_override=3,
        include_structure_checks=False,
        include_peak_max_check=False,
        include_pass1_progression=False,
        include_phase_quality=True,
    )
    codes = [i["code"] for i in issues]
    assert "phase_peak_not_reached_in_build" in codes


def test_validate_long_run_curve_peak_max_below_adaptive_target(
    marathon_cfg: MarathonConfig,
) -> None:
    """Orchestrator-style max long run vs peak_target - margin (default 1.0 mi)."""
    curve = [8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 12.0, 10.0, 8.0, 6.0]
    issues = validate_long_run_curve(
        curve,
        marathon_cfg,
        spine_rows=None,
        expected_start_miles=None,
        peak_target_miles=20.0,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=int(marathon_cfg.cutback_every),
        taper_weeks_override=int(marathon_cfg.taper_weeks),
        include_structure_checks=False,
        include_peak_max_check=True,
        include_pass1_progression=False,
        include_phase_quality=False,
    )
    assert [i["code"] for i in issues] == ["peak_not_reached_max_below_target"]


def test_validate_long_run_curve_bad_taper_increase(
    marathon_cfg: MarathonConfig,
) -> None:
    """Taper weeks should not jump up by more than tolerance vs prior taper week."""
    peak = 18.0
    curve = [
        10.0,
        11.0,
        12.0,
        13.0,
        14.0,
        15.0,
        16.0,
        17.0,
        18.0,
        14.0,
        10.0,
        16.0,
    ]
    issues = validate_long_run_curve(
        curve,
        marathon_cfg,
        spine_rows=None,
        expected_start_miles=None,
        peak_target_miles=peak,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=int(marathon_cfg.cutback_every),
        taper_weeks_override=3,
        include_structure_checks=False,
        include_peak_max_check=False,
        include_pass1_progression=False,
        include_phase_quality=True,
    )
    codes = [i["code"] for i in issues]
    assert "phase_taper_increase" in codes


def test_validate_long_run_curve_pass1_week1_mismatch(
    marathon_cfg: MarathonConfig,
) -> None:
    weeks = [
        {"week_number": 1, "long_run_miles": 10.0, "is_cutback": False},
        {"week_number": 2, "long_run_miles": 11.0, "is_cutback": False},
    ]
    curve = [10.0, 11.0]
    issues = validate_long_run_curve(
        curve,
        marathon_cfg,
        spine_rows=weeks,
        expected_start_miles=12.0,
        peak_target_miles=20.0,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=int(marathon_cfg.cutback_every),
        taper_weeks_override=int(marathon_cfg.taper_weeks),
        include_structure_checks=False,
        include_peak_max_check=False,
        include_pass1_progression=True,
        include_phase_quality=False,
    )
    assert len(issues) == 1
    assert issues[0]["code"] == "pass1_week1_mismatch"
    assert issues[0]["severity"] == "error"


def test_validate_long_run_curve_structure_missing_phase(
    marathon_cfg: MarathonConfig,
) -> None:
    weeks = [{"week_number": 1, "long_run_miles": 10.0}]
    issues = validate_long_run_curve(
        [10.0],
        marathon_cfg,
        spine_rows=weeks,
        expected_start_miles=None,
        peak_target_miles=20.0,
        taper_ratios_override=list(marathon_cfg.taper_ratios),
        cutback_every_override=int(marathon_cfg.cutback_every),
        taper_weeks_override=int(marathon_cfg.taper_weeks),
        include_structure_checks=True,
        include_peak_max_check=False,
        include_pass1_progression=False,
        include_phase_quality=False,
    )
    assert issues[0]["code"] == "structure_missing_phase"
