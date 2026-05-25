"""Weekly insight z2_pace_band uses pace_progress (goal easy pace), not week-over-week trend."""

from __future__ import annotations

from src.smartcoach_mobile_coach.runner_profile.models import PaceZoneBand
from src.smartcoach_mobile_coach.weekly_insights_service import (
    _compute_easy_system_pipeline,
)


def _target_easy_pace() -> PaceZoneBand:
    """9:00/mi goal easy pace (540 sec/mi)."""
    return PaceZoneBand(low_sec=540, high_sec=540, display="9:00")


def test_z2_pace_band_slow_vs_target_is_yellow_despite_wow_improvement():
    """9:15/mi vs 9:00 target is yellow; vs prior 9:30/mi WoW trend would be green."""
    kpis = {
        "avg_hr": 130.0,
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.25,
        "efficiency": 1.2,
    }
    prior = {
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.5,
        "efficiency": 1.1,
        "easy_avg_hr": 130.0,
        "hr_drift_band": "green",
        "z2_pace_band": "green",
        "easy_avg_hr_band": "green",
        "efficiency_band": "green",
        "overall_band": "green",
    }
    out = _compute_easy_system_pipeline(
        kpis, prior, target_easy_pace=_target_easy_pace()
    )
    assert out["bands"]["z2_pace"] == "yellow"


def test_z2_pace_band_at_or_faster_than_target_is_green():
    kpis = {
        "avg_hr": 130.0,
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.0,
        "efficiency": 1.2,
    }
    out = _compute_easy_system_pipeline(
        kpis, prior=None, target_easy_pace=_target_easy_pace()
    )
    assert out["bands"]["z2_pace"] == "green"


def test_z2_pace_band_null_without_goal_easy_pace_target():
    kpis = {
        "avg_hr": 130.0,
        "hr_drift_pct": 2.0,
        "z2_pace_min_per_mi": 9.0,
        "efficiency": 1.2,
    }
    out = _compute_easy_system_pipeline(kpis, prior=None, target_easy_pace=None)
    assert out["bands"]["z2_pace"] is None
